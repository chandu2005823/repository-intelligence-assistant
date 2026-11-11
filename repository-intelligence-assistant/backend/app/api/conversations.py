import logging
import re
import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.conversation_service import (
    add_exchange,
    create_conversation,
    get_conversation,
    list_conversations,
    list_messages,
)
from app.services.llm_service import LLMServiceError, generate_repository_answer
from app.services.vector_store import search_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Conversations"])


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class SendMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


def _resolve_followup_query(previous_messages: list[dict], latest_message: str) -> str:
    cleaned = (latest_message or '').strip()
    if not cleaned:
        return cleaned

    previous_user_questions = [
        message['content']
        for message in previous_messages
        if message.get('role') == 'user' and (message.get('content') or '').strip()
    ]

    if not previous_user_questions:
        return cleaned

    lower = cleaned.lower()
    if not re.search(r'\b(this|that|these|those|it|they|them|their|he|she|class|function|file|repository|constructor|method)\b', lower):
        return cleaned

    last_question = previous_user_questions[-1]
    if len(cleaned.split()) <= 12:
        return f"{last_question} {cleaned}".strip()

    return cleaned


@router.post("/repositories/{repository_id}/conversations")
def create_repository_conversation(repository_id: str, request: CreateConversationRequest):
    normalized_id = (repository_id or '').strip()
    if not normalized_id:
        raise HTTPException(status_code=400, detail='Repository ID is required.')

    try:
        return create_conversation(normalized_id, request.title)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/repositories/{repository_id}/conversations")
def list_repository_conversations(repository_id: str):
    normalized_id = (repository_id or '').strip()
    if not normalized_id:
        raise HTTPException(status_code=400, detail='Repository ID is required.')

    return {
        'repository_id': normalized_id,
        'conversations': list_conversations(normalized_id),
    }


@router.get("/repositories/{repository_id}/conversations/{conversation_id}")
def get_repository_conversation(repository_id: str, conversation_id: str):
    normalized_id = (repository_id or '').strip()
    if not normalized_id:
        raise HTTPException(status_code=400, detail='Repository ID is required.')

    conversation = get_conversation(normalized_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail='Conversation not found.')

    return conversation


@router.post("/repositories/{repository_id}/conversations/{conversation_id}/messages")
def send_repository_message(repository_id: str, conversation_id: str, request: SendMessageRequest):
    normalized_id = (repository_id or '').strip()
    if not normalized_id:
        raise HTTPException(status_code=400, detail='Repository ID is required.')

    conversation = get_conversation(normalized_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail='Conversation not found.')

    recent_messages = list_messages(conversation_id, limit=10)
    resolved_query = _resolve_followup_query(recent_messages, request.message)
    try:
        retrieved_chunks = search_repository(
            repository_id=normalized_id,
            query=resolved_query,
            top_k=5,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.error(
            'Repository retrieval failed: exception_type=%s',
            type(error).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail={
                'code': 'repository_retrieval_failed',
                'message': 'Repository search failed. Check the backend logs and try again.',
            },
        ) from error

    try:
        answer = generate_repository_answer(
            question=resolved_query,
            retrieved_chunks=retrieved_chunks,
        )
    except LLMServiceError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={'code': error.code, 'message': error.message},
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.error(
            'Repository answer generation failed: exception_type=%s',
            type(error).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail={
                'code': 'repository_answer_failed',
                'message': 'Answer generation failed unexpectedly. Check the backend logs and try again.',
            },
        ) from error

    try:
        user_message, assistant_message = add_exchange(
            conversation_id,
            request.message,
            answer,
            assistant_metadata={
                'repository_id': normalized_id,
                'resolved_question': resolved_query,
                'source_count': len(retrieved_chunks),
                'sources': [
                    {
                        'file_path': chunk.get('file_path'),
                        'chunk_type': chunk.get('chunk_type'),
                        'symbol_name': chunk.get('symbol_name'),
                        'start_line': chunk.get('start_line'),
                        'end_line': chunk.get('end_line'),
                        'distance': chunk.get('distance'),
                    }
                    for chunk in retrieved_chunks
                ],
            },
        )
    except sqlite3.Error as error:
        logger.error(
            'Could not persist repository conversation exchange: exception_type=%s',
            type(error).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail={
                'code': 'conversation_storage_failed',
                'message': 'The answer was generated but could not be saved to conversation history.',
            },
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        'repository_id': normalized_id,
        'conversation_id': conversation_id,
        'user_message': user_message,
        'assistant_message': assistant_message,
        'resolved_question': resolved_query,
    }

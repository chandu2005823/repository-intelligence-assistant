# For Your Friend: How to Use This Project

## Quick Answer

**Why don't the repository IDs work on my laptop?**

Because each computer stores its own data locally:
- Your data: `backend/data/repositories/` on your laptop
- Friend's data: `backend/data/repositories/` on their laptop

They're **completely separate**. Each machine needs to upload its own repositories.

## Quick Start (For Your Friend)

### 1. Clone the Project

```bash
git clone https://github.com/chandu2005823/repository-intelligence-assistant.git
cd repository-intelligence-assistant
```

### 2. Backend Setup (5 minutes)

```bash
cd repository-intelligence-assistant/backend
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add your Groq API key:
```
GROQ_API_KEY=your_actual_key_here
```

Get it from: https://console.groq.com

Start backend:
```bash
python main.py
```

### 3. Frontend Setup (2 minutes)

Open a **new terminal**:

```bash
cd repository-intelligence-assistant/frontend
npm install
npm run dev
```

### 4. Open Application

Go to: http://127.0.0.1:5173

### 5. Upload a Repository

- Click "Choose ZIP archive"
- Select a ZIP file of code
- Click "Upload repository"
- A **NEW** repository ID will be generated
- Use that ID to search and analyze

## Important Notes

✅ **Each machine is independent**
- Your laptop has its own data
- Friend's laptop has its own data
- They don't sync

✅ **Every upload creates a NEW repository ID**
- Same repository ZIP on your machine = your repo ID
- Same repository ZIP on friend's machine = different repo ID

✅ **Data is stored locally**
- No data is sent to the cloud
- All conversations are local
- All indexed files are local

## Troubleshooting for Your Friend

### "pip: command not found"
→ Install Python from https://python.org/

### "npm: command not found"  
→ Install Node.js from https://nodejs.org/

### "Repository ID not found"
→ This is expected! Upload a new ZIP file to get a new ID on their machine

### "Invalid API key"
→ Check `.env` file has correct Groq API key from https://console.groq.com

### "Port already in use"
→ Close any other running instances and try again

## File Structure to Know

```
repository-intelligence-assistant/
├── backend/              ← Run: python main.py
│   └── data/            ← Local data (not in git)
├── frontend/            ← Run: npm run dev
├── README.md            ← Project overview
├── SETUP_GUIDE.md       ← Detailed setup instructions
└── .env.example         ← Copy this to .env and add API key
```

## Key Takeaway

🎯 **Each computer is a separate instance with its own data**

- Your data stays on your laptop
- Friend's data stays on their laptop
- They can't access each other's repository IDs
- **This is by design for security and privacy**

## Features They Can Use

1. ✅ Upload their own repositories
2. ✅ Search their code with AI
3. ✅ Ask questions about their code
4. ✅ Explore dependencies
5. ✅ Get code reviews
6. ✅ View code intelligence

## Getting Help

- Read `SETUP_GUIDE.md` for detailed instructions
- Check error messages in the terminal
- Verify API key is correct
- Try uploading a different repository

---

**Summary**: Your friend needs to set up the project on their laptop, get their own API key, and upload their own repositories. Each machine works independently with its own data.

Good luck! 🚀

# Repository Intelligence Assistant - Testing Guide

## ✅ Test Repository Successfully Uploaded!

**Repository ID:** `894b23d9ccb241e2825e263ed39c9d62`

**Project:** User Management System (Python Flask application)

**Contents:**
- 8 Python files (7 source files + 1 config)
- 1 Markdown README
- 30 functions
- 2 classes (UserManager, DatabaseConnection)
- 428 total lines of code
- 34 code chunks indexed

---

## 🎯 What to Test in Each Section

### **1️⃣ REPOSITORY SEARCH** - Hybrid Search Engine
**Test Location:** Frontend → Search Tab (or API: `/api/repositories/search`)

**What to Search For:**

#### Query 1: Search for Authentication
```
Query: "authentication"
Expected Results:
- hash_password() function from auth/login.py
- authenticate_user() function from auth/login.py
- login() endpoint from auth/login.py
- verify_password() helper function
```

**Why It Works:** 
- Semantic matching on "authentication" and related security keywords
- Keyword matching on "auth" in function names
- File path matching on `auth/` directory

---

#### Query 2: Search for Database Operations
```
Query: "database connection insert user"
Expected Results:
- insert_user() method from DatabaseConnection class
- init_database() function
- get_database_connection() factory function
- DatabaseConnection class definition
```

**Why It Works:**
- Semantic understanding of database patterns
- Keyword overlap on "database", "connection", "insert", "user"
- Symbol name boosting for exact matches

---

#### Query 3: Search for Flask Routes
```
Query: "login route flask"
Expected Results:
- login() function decorated with @login_blueprint.route
- logout() function
- list_users() endpoint
- get_user() endpoint
```

**Why It Works:**
- Semantic matching on "route" and "login"
- Keyword matching on "route" in comments and decorators

---

### **2️⃣ AI ASSISTANT** - Question Answering
**Test Location:** Frontend → Chat Tab (or API: `/api/repositories/ask`)

**What to Ask:**

#### Question 1: Architecture
```
Question: "What is the architecture of this application?"
Expected Answer Should Include:
- Main entry point is main.py
- Uses Flask framework
- Authentication module in auth/login.py
- User management in users/manager.py
- Database connection in database/connection.py
- Three packages: auth, users, database
```

**What You'll Learn:**
- ✅ AI can understand and explain multi-file architecture
- ✅ Source citations show where information comes from
- ✅ [SOURCE N] references point to specific code chunks

---

#### Question 2: Security Features
```
Question: "How does the authentication system work?"
Expected Answer Should Include:
- Uses bcrypt for password hashing
- hash_password() creates salt and hashes
- verify_password() compares hashed passwords
- authenticate_user() validates email and password
- Returns user object on success, None on failure
```

**What You'll Learn:**
- ✅ AI extracts function logic from code
- ✅ Explains security mechanisms in plain English
- ✅ Shows code flow and dependencies

---

#### Question 3: Follow-up Question (Tests Context)
```
First Question: "What does the UserManager class do?"
Answer: [Should explain CRUD operations]

Follow-up: "How is it used in the API endpoints?"
Expected Answer Should Include:
- UserManager instantiated in route handlers
- create_user() in POST /users endpoint
- get_user() in GET /users/<id> endpoint
- update_user() in PUT /users/<id> endpoint
- list_users() in GET /users endpoint
```

**What You'll Learn:**
- ✅ Follow-up questions resolved using conversation context
- ✅ AI connects related code across multiple files
- ✅ Shows how components interact

---

### **3️⃣ DEPENDENCY EXPLORER** - Import Resolution
**Test Location:** Frontend → Dependencies Tab (or API: `/api/repositories/{id}/dependencies`)

**What to Look For:**

#### Dependency Graph Visualization

**Expected Nodes (Files):**
```
- main.py
- auth/login.py
- auth/__init__.py
- users/manager.py
- users/__init__.py
- database/connection.py
- database/__init__.py
- README.md
```

**Expected Edges (Import Relationships):**
```
main.py
  → imports from: auth/login.py (login_blueprint)
  → imports from: users/manager.py (users_blueprint)
  → imports from: database/connection.py (init_database)

auth/login.py
  → imports from: database/connection.py (get_user_by_email)

users/manager.py
  → imports from: database/connection.py (get_database_connection)
  → imports from: auth/login.py (hash_password)

database/connection.py
  → external: sqlite3, subprocess [UNRESOLVED: shown differently]
```

**External/Unresolved Imports:**
```
- flask
- bcrypt
- sqlite3
- subprocess
- jwt
- sqlalchemy
```

**What You'll Learn:**
- ✅ How to visualize code structure
- ✅ Identify circular dependencies (none here, but system can detect)
- ✅ Understand which modules depend on which
- ✅ See entry points (main.py imports everything)

---

### **4️⃣ CODE INTELLIGENCE** - Call Graphs & Impact Analysis
**Test Location:** Frontend → Intelligence Tab (or API: `/api/repositories/{id}/intelligence`)

**What to Explore:**

#### All Definitions
```
Expected Functions (30 total):
- hash_password() at auth/login.py:12
- verify_password() at auth/login.py:25
- authenticate_user() at auth/login.py:38
- login() at auth/login.py:60
- logout() at auth/login.py:95
- home() at main.py:22
- health_check() at main.py:27
- UserManager.__init__() at users/manager.py:15
- UserManager.create_user() at users/manager.py:19
- UserManager.get_user() at users/manager.py:46
- ... [20 more functions]

Expected Classes (2 total):
- UserManager at users/manager.py:12
- DatabaseConnection at database/connection.py:39
```

---

#### Search by Function Name
```
Query: "authenticate_user"
Expected Results:
- Definition: authenticate_user() at auth/login.py:38
- Calls: 
  - Called by login() at auth/login.py:66
  - Called by main code (if any)
- Callers: login() function

Impact:
- If authenticate_user() changes, login() is affected
- If you refactor this function, know login() depends on it
```

**What You'll Learn:**
- ✅ Find all definitions of a function/class
- ✅ See who calls this function (reversed call graph)
- ✅ Understand refactoring impact
- ✅ Navigate code relationships

---

#### Search by File Path
```
Query: Filter by "auth/login.py"
Expected Results:
- All definitions in auth/login.py
- All functions: hash_password, verify_password, authenticate_user, login, logout
- All calls made by these functions
```

**What You'll Learn:**
- ✅ See all code in a specific file
- ✅ Understand a module's public interface
- ✅ See internal relationships within a module

---

### **5️⃣ CODE REVIEW** - Static Security Analysis
**Test Location:** Frontend → Review Tab (or API: `/api/repositories/{id}/review`)

**Expected Findings:**

#### Finding 1: eval() Usage ⚠️
```
Severity: Medium
File: main.py:34
Code: debug_mode = eval(input("Enter debug mode (True/False): "))
Issue: Dynamic code execution via eval()
Explanation: 
  - eval() executes arbitrary Python code
  - If input comes from untrusted source, dangerous
  - Can execute malicious code

Suggestion:
  - Use safer alternatives like ast.literal_eval()
  - Or parse input manually with validation
  - Never use eval() with user input
```

---

#### Finding 2: shell=True in subprocess ⚠️
```
Severity: High
File: database/connection.py:146
Code: subprocess.run(command, shell=True, check=True)
Issue: Subprocess uses shell with command injection risk
Explanation:
  - shell=True allows command injection
  - Variable substitution in f-string is dangerous
  - If backup_path contains shell metacharacters, vulnerability

Suggestion:
  - Use subprocess with shell=False (default)
  - Pass command as list: ["cp", src, dest]
  - Validate all inputs before using in commands
```

---

#### Finding 3: Missing Error Handling ℹ️
```
Status: Could be improved
File: users/manager.py:136
Issue: Exception caught but only message shown
Suggestion:
  - Log the full exception details
  - Different error codes for different failure types
  - Return more specific error messages to client
```

---

#### AI Explanation (if configured with LLM)
```
The AI would generate explanations for each finding:

"The eval() call on line 34 of main.py is a significant security risk. 
eval() executes arbitrary Python code, which means if an attacker can 
control the input, they can execute any Python code in your application. 
In this case, the input comes from user input at runtime, which is even 
more dangerous because a local user could inject malicious code. 

To fix this, replace eval() with ast.literal_eval() which safely evaluates 
a limited subset of Python literal structures [SOURCE 1], or parse the 
input string manually to extract just the boolean value."
```

---

## 📊 What the Numbers Mean

From the upload response:

```json
{
  "file_count": 8,                          // 8 files analyzed
  "total_lines": 428,                       // 428 lines of code
  "python_file_count": 7,                   // 7 Python files
  "total_functions": 30,                    // 30 functions defined
  "total_classes": 2,                       // 2 classes defined
  "chunk_count": 34,                        // 34 chunks for search
  "indexed_chunks": 34,                     // All 34 indexed in ChromaDB
}
```

**What This Means:**
- ✅ 100% of code was successfully indexed
- ✅ 34 searchable chunks created (max 80 lines each)
- ✅ No syntax errors
- ✅ All functions and classes extracted via AST

---

## 🧪 Suggested Test Workflow

### Step 1: Search (5 min)
```
1. Try Query: "authentication"
2. Try Query: "user management"
3. Try Query: "database operations"
→ Verify results are relevant
→ Check if code chunks are accurate
```

### Step 2: Ask Questions (10 min)
```
1. Ask: "What is this project about?"
2. Ask: "How does password security work?"
3. Ask: "What are the API endpoints?"
→ Read the answer
→ Click on [SOURCE N] links to see code
→ Verify citations are accurate
```

### Step 3: Explore Dependencies (5 min)
```
1. Open Dependencies tab
2. Look at the graph structure
3. Find main.py at the top (imports everything)
4. Follow arrows to understand flow
→ Trace from main.py → auth → login
→ Trace from main.py → users → database
```

### Step 4: Understand Call Flow (5 min)
```
1. Open Intelligence tab
2. Search for: "authenticate_user"
3. See who calls it (login function)
4. See what it calls (verify_password, get_user_by_email)
5. Click "Show Impact" to see broader effects
```

### Step 5: Review Security (5 min)
```
1. Open Review tab
2. Read findings (eval() and subprocess warnings)
3. Click AI Explanation
4. See which files have issues
5. Understand the recommendations
```

---

## 📝 Repository Details

**Project Type:** User Management System  
**Framework:** Flask (Python web framework)  
**Database:** SQLite  
**Authentication:** Bcrypt password hashing  
**Features:**
- User login/logout
- User CRUD operations
- Password hashing
- Database management
- Flask blueprints for modularity

**File Structure:**
```
main.py                    - App entry point
auth/login.py             - Authentication logic
users/manager.py          - User management CRUD
database/connection.py    - Database operations
(+ __init__.py files)     - Package markers
README.md                 - Documentation
```

**Security Issues Intentionally Included (for testing):**
1. ✗ eval() for user input (main.py line 34)
2. ✗ subprocess with shell=True (database/connection.py line 146)
3. ✗ No rate limiting on login
4. ✗ Secrets in code comments

---

## 🎯 Success Criteria

You'll know everything is working when:

- ✅ Search returns relevant code chunks
- ✅ AI answers questions with source citations
- ✅ Dependencies show the import graph
- ✅ Intelligence reveals function calls and definitions
- ✅ Review identifies the security issues
- ✅ Each [SOURCE N] link matches cited code

---

## 🚀 Next Steps

1. Test all 5 features with this repository
2. Try searching for different keywords
3. Ask various questions about the code
4. Explore the dependency graph
5. Examine the security findings
6. Upload your own repository to test

---

**Repository ID to Use:** `894b23d9ccb241e2825e263ed39c9d62`

Copy this ID and paste it into the application when prompted!

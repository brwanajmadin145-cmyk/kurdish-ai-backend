import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import os
import hashlib
from dotenv import load_dotenv

# 🔒 LOAD ENVIRONMENT VARIABLES
load_dotenv()

# ✅ GET DATABASE URL FROM ENVIRONMENT
DATABASE_URL = os.getenv("DATABASE_URL")

@contextmanager
def get_db():
    # بڕوا گیان، لێرەدا دڵنیابە نیشانەی " لە دوای یەکسان و لە کۆتایی هەیە
    DATABASE_URL = "postgresql://postgres:PGJJyfNDbeAqdsjarzhmlHJDAjrVolMh@shortline.proxy.rlwy.net:10741/railway"
    
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        yield conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()


def init_database():
    """Create all database tables"""
    print("🔄 Initializing PostgreSQL database...")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id VARCHAR(255) PRIMARY KEY,
                email VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Conversations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id SERIAL PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id SERIAL PRIMARY KEY,
                conversation_id INTEGER REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                user_id VARCHAR(255) NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Images table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                image_id SERIAL PRIMARY KEY,
                conversation_id INTEGER,
                user_id VARCHAR(255) NOT NULL,
                image_url TEXT NOT NULL,
                prompt TEXT,
                image_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Files table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                file_id SERIAL PRIMARY KEY,
                conversation_id INTEGER,
                user_id VARCHAR(255) NOT NULL,
                file_url TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Feedback table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                feedback_id SERIAL PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                user_email VARCHAR(255),
                rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 🔒 PRIVACY TABLES 🔒
        
        # Privacy passwords
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS privacy_passwords (
                user_id VARCHAR(255) PRIMARY KEY,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Privacy conversations (separate from normal!)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS privacy_conversations (
                conversation_id SERIAL PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Privacy messages (separate from normal!)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS privacy_messages (
                message_id SERIAL PRIMARY KEY,
                conversation_id INTEGER REFERENCES privacy_conversations(conversation_id) ON DELETE CASCADE,
                user_id VARCHAR(255) NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Privacy images (separate from normal!)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS privacy_images (
                image_id SERIAL PRIMARY KEY,
                conversation_id INTEGER,
                user_id VARCHAR(255) NOT NULL,
                image_url TEXT NOT NULL,
                prompt TEXT,
                image_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Privacy files (separate from normal!)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS privacy_files (
                file_id SERIAL PRIMARY KEY,
                conversation_id INTEGER,
                user_id VARCHAR(255) NOT NULL,
                file_url TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_conversations ON conversations(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversation_messages ON messages(conversation_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_images ON images(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_files ON files(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_privacy_conversations ON privacy_conversations(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_privacy_messages ON privacy_messages(conversation_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_privacy_images ON privacy_images(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_privacy_files ON privacy_files(user_id)')
        
        conn.commit()
        cursor.close()
        
    print("✅ All database tables initialized (including Privacy)!")


# ===================== CONVERSATION FUNCTIONS =====================

def create_conversation(user_id: str, title: str):
    """Create new conversation"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversations (user_id, title) VALUES (%s, %s) RETURNING conversation_id",
            (user_id, title)
        )
        conversation_id = cursor.fetchone()['conversation_id']
        conn.commit()
        cursor.close()
        return conversation_id


def save_message(user_id: str, conversation_id: int, role: str, content: str):
    """Save message to conversation"""
    if content:
        content = content.replace('\x00', '').replace('\0', '')
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (conversation_id, user_id, role, content) VALUES (%s, %s, %s, %s)",
            (conversation_id, user_id, role, content)
        )
        cursor.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE conversation_id = %s",
            (conversation_id,)
        )
        conn.commit()
        cursor.close()


def get_conversation_history(conversation_id: int, limit: int = 50):
    """Get conversation messages"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT role, content, timestamp
            FROM messages 
            WHERE conversation_id = %s 
            ORDER BY timestamp ASC
            LIMIT %s
        """, (conversation_id, limit))
        
        rows = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in rows]


def get_all_conversations(user_id: str):
    """Get all user conversations"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT conversation_id, title, created_at, updated_at
            FROM conversations 
            WHERE user_id = %s 
            ORDER BY updated_at DESC
        """, (user_id,))
        
        rows = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in rows]


# ===================== IMAGE FUNCTIONS =====================

def save_image(user_id: str, conversation_id: int, image_url: str, prompt: str = "", image_type: str = "generated"):
    """Save image"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO images (conversation_id, user_id, image_url, prompt, image_type) VALUES (%s, %s, %s, %s, %s)",
            (conversation_id, user_id, image_url, prompt, image_type)
        )
        conn.commit()
        cursor.close()


def get_user_images(user_id: str):
    """Get all user images"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT image_id, image_url, prompt, image_type, created_at
            FROM images 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (user_id,))
        
        rows = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in rows]


# ===================== FILE FUNCTIONS =====================

def save_file(user_id: str, conversation_id: int, file_url: str, file_name: str, file_type: str):
    """Save file"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO files (conversation_id, user_id, file_url, file_name, file_type) VALUES (%s, %s, %s, %s, %s)",
            (conversation_id, user_id, file_url, file_name, file_type)
        )
        conn.commit()
        cursor.close()


def get_user_files(user_id: str):
    """Get all user files"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT file_id, file_url, file_name, file_type, created_at
            FROM files 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (user_id,))
        
        rows = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in rows]


# ===================== FEEDBACK FUNCTIONS =====================

def save_feedback(user_id: str, user_email: str, rating: int, message: str):
    """Save feedback"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO feedback (user_id, user_email, rating, message)
            VALUES (%s, %s, %s, %s)
            RETURNING feedback_id
        """, (user_id, user_email, rating, message))
        
        feedback_id = cursor.fetchone()['feedback_id']
        conn.commit()
        cursor.close()
        return feedback_id


def get_all_feedback():
    """Get all feedback"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT feedback_id, user_id, user_email, rating, message,
                   to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at
            FROM feedback
            ORDER BY created_at DESC
        """)
        
        feedback_list = cursor.fetchall()
        cursor.close()
        return feedback_list


def reset_user_account(user_id: str):
    """Delete all user data (NORMAL ONLY - not privacy)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM conversations WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM images WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM files WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM feedback WHERE user_id = %s", (user_id,))
        conn.commit()
        cursor.close()
        return True


# ===================== 🔒 PRIVACY FUNCTIONS 🔒 =====================

def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


def set_privacy_password(user_id: str, password: str):
    """Set or update privacy password"""
    password_hash = hash_password(password)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO privacy_passwords (user_id, password_hash)
            VALUES (%s, %s)
            ON CONFLICT (user_id)
            DO UPDATE SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
        """, (user_id, password_hash, password_hash))
        conn.commit()
        cursor.close()


def check_privacy_password(user_id: str, password: str) -> bool:
    """Check if privacy password is correct"""
    password_hash = hash_password(password)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT password_hash FROM privacy_passwords WHERE user_id = %s",
            (user_id,)
        )
        result = cursor.fetchone()
        cursor.close()
        
        if result:
            return result['password_hash'] == password_hash
        return False


def has_privacy_password(user_id: str) -> bool:
    """Check if user has set privacy password"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id FROM privacy_passwords WHERE user_id = %s",
            (user_id,)
        )
        result = cursor.fetchone()
        cursor.close()
        return result is not None


# Privacy conversation functions
def create_privacy_conversation(user_id: str, title: str):
    """Create new PRIVACY conversation"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO privacy_conversations (user_id, title) VALUES (%s, %s) RETURNING conversation_id",
            (user_id, title)
        )
        conversation_id = cursor.fetchone()['conversation_id']
        conn.commit()
        cursor.close()
        return conversation_id


def save_privacy_message(user_id: str, conversation_id: int, role: str, content: str):
    """Save message to PRIVACY conversation"""
    if content:
        content = content.replace('\x00', '').replace('\0', '')
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO privacy_messages (conversation_id, user_id, role, content) VALUES (%s, %s, %s, %s)",
            (conversation_id, user_id, role, content)
        )
        cursor.execute(
            "UPDATE privacy_conversations SET updated_at = CURRENT_TIMESTAMP WHERE conversation_id = %s",
            (conversation_id,)
        )
        conn.commit()
        cursor.close()


def get_privacy_conversation_history(conversation_id: int, limit: int = 50):
    """Get PRIVACY conversation messages"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT role, content, timestamp
            FROM privacy_messages 
            WHERE conversation_id = %s 
            ORDER BY timestamp ASC
            LIMIT %s
        """, (conversation_id, limit))
        
        rows = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in rows]


def get_all_privacy_conversations(user_id: str):
    """Get all PRIVACY conversations"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT conversation_id, title, created_at, updated_at
            FROM privacy_conversations 
            WHERE user_id = %s 
            ORDER BY updated_at DESC
        """, (user_id,))
        
        rows = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in rows]


def save_privacy_image(user_id: str, conversation_id: int, image_url: str, prompt: str = "", image_type: str = "generated"):
    """Save PRIVACY image"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO privacy_images (conversation_id, user_id, image_url, prompt, image_type) VALUES (%s, %s, %s, %s, %s)",
            (conversation_id, user_id, image_url, prompt, image_type)
        )
        conn.commit()
        cursor.close()


def get_user_privacy_images(user_id: str):
    """Get all PRIVACY images"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT image_id, image_url, prompt, image_type, created_at
            FROM privacy_images 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (user_id,))
        
        rows = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in rows]


def save_privacy_file(user_id: str, conversation_id: int, file_url: str, file_name: str, file_type: str):
    """Save PRIVACY file"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO privacy_files (conversation_id, user_id, file_url, file_name, file_type) VALUES (%s, %s, %s, %s, %s)",
            (conversation_id, user_id, file_url, file_name, file_type)
        )
        conn.commit()
        cursor.close()


def get_user_privacy_files(user_id: str):
    """Get all PRIVACY files"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT file_id, file_url, file_name, file_type, created_at
            FROM privacy_files 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (user_id,))
        
        rows = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in rows]


def reset_privacy_data(user_id: str):
    """Delete ALL privacy data (password + conversations + images + files)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM privacy_conversations WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM privacy_images WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM privacy_files WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM privacy_passwords WHERE user_id = %s", (user_id,))
        conn.commit()
        cursor.close()
        return True


if __name__ == "__main__":
    init_database()

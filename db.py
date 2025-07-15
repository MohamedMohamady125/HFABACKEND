from app.utils.tokens import create_reset_token as token_creator

def get_user_by_email(email: str):
    # Dummy user DB — replace this with real database query logic
    user_db = {"coach@example.com": {"id": 42, "email": "coach@example.com"}}
    return user_db.get(email)

def create_reset_token(user_id: int):
    return token_creator(user_id)
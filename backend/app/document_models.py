from app.repositories.repository import Transaction, User, Wallet

DOCUMENT_MODELS: list[type] = [
    User,
    Wallet,
    Transaction,
]

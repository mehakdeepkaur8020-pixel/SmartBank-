from sqlalchemy.orm import Session
from typing import List
from app.models.models import Notification

def create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    notification_type: str = "INFO"
) -> Notification:
    """Create a user notification."""
    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        is_read=False
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif

def get_user_notifications(db: Session, user_id: int, limit: int = 10) -> List[Notification]:
    """Retrieve the latest notifications for a user."""
    return db.query(Notification).filter(
        Notification.user_id == user_id
    ).order_by(Notification.created_at.desc()).limit(limit).all()

def mark_notification_as_read(db: Session, notification_id: int, user_id: int) -> bool:
    """Mark a notification as read with ownership verification."""
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user_id
    ).first()
    if notif:
        notif.is_read = True
        db.commit()
        return True
    return False

def mark_all_notifications_as_read(db: Session, user_id: int) -> int:
    """Mark all notifications as read for a user."""
    updated = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return updated

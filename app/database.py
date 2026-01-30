"""Database models and connection for AI Coding Agent."""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from .config import settings

# Create database engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


class IterationStatus(str, Enum):
    """Status of an iteration cycle."""
    RUNNING = "running"
    WAITING_CI = "waiting_ci"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IssueIteration(Base):
    """Model for tracking issue iteration state."""
    
    __tablename__ = "issue_iterations"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # GitHub identifiers
    repo_full_name = Column(String, nullable=False, index=True)  # owner/repo
    issue_number = Column(Integer, nullable=False, index=True)
    pr_number = Column(Integer, nullable=True)
    installation_id = Column(Integer, nullable=False)
    
    # Iteration tracking
    current_iteration = Column(Integer, default=0)
    max_iterations = Column(Integer, default=5)
    status = Column(String, default=IterationStatus.RUNNING)
    
    # Content
    issue_title = Column(String, nullable=True)
    issue_body = Column(Text, nullable=True)
    branch_name = Column(String, nullable=True)
    
    # Review feedback
    last_review_score = Column(Integer, nullable=True)
    last_review_recommendation = Column(String, nullable=True)
    last_review_feedback = Column(Text, nullable=True)
    
    # CI status
    last_ci_status = Column(String, nullable=True)  # success, failure, pending
    last_ci_conclusion = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Flags
    is_active = Column(Boolean, default=True)


async def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DatabaseManager:
    """Database operations manager."""
    
    def __init__(self):
        self.session_factory = SessionLocal
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.session_factory()
    
    def get_active_iteration(
        self, 
        repo_full_name: str, 
        issue_number: int
    ) -> Optional[IssueIteration]:
        """Get active iteration for an issue."""
        with self.get_session() as db:
            return db.query(IssueIteration).filter(
                IssueIteration.repo_full_name == repo_full_name,
                IssueIteration.issue_number == issue_number,
                IssueIteration.is_active == True
            ).first()
    
    def create_iteration(
        self,
        repo_full_name: str,
        issue_number: int,
        installation_id: int,
        issue_title: str = None,
        issue_body: str = None,
        max_iterations: int = None
    ) -> IssueIteration:
        """Create a new iteration record."""
        with self.get_session() as db:
            # Deactivate any existing iterations for this issue
            existing = db.query(IssueIteration).filter(
                IssueIteration.repo_full_name == repo_full_name,
                IssueIteration.issue_number == issue_number,
                IssueIteration.is_active == True
            ).all()
            
            for iteration in existing:
                iteration.is_active = False
            
            # Create new iteration
            iteration = IssueIteration(
                repo_full_name=repo_full_name,
                issue_number=issue_number,
                installation_id=installation_id,
                issue_title=issue_title,
                issue_body=issue_body,
                max_iterations=max_iterations or settings.max_iterations,
                current_iteration=0,
                status=IterationStatus.RUNNING
            )
            
            db.add(iteration)
            db.commit()
            db.refresh(iteration)
            return iteration
    
    def update_iteration(
        self,
        iteration_id: int,
        **kwargs
    ) -> Optional[IssueIteration]:
        """Update iteration record."""
        with self.get_session() as db:
            iteration = db.query(IssueIteration).filter(
                IssueIteration.id == iteration_id
            ).first()
            
            if not iteration:
                return None
            
            for key, value in kwargs.items():
                if hasattr(iteration, key):
                    setattr(iteration, key, value)
            
            iteration.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(iteration)
            return iteration
    
    def increment_iteration(self, iteration_id: int) -> Optional[IssueIteration]:
        """Increment iteration counter."""
        with self.get_session() as db:
            iteration = db.query(IssueIteration).filter(
                IssueIteration.id == iteration_id
            ).first()
            
            if not iteration:
                return None
            
            iteration.current_iteration += 1
            iteration.updated_at = datetime.utcnow()
            
            # Check if we've reached max iterations
            if iteration.current_iteration >= iteration.max_iterations:
                iteration.status = IterationStatus.FAILED
                iteration.completed_at = datetime.utcnow()
            
            db.commit()
            db.refresh(iteration)
            return iteration
    
    def complete_iteration(
        self,
        iteration_id: int,
        status: IterationStatus = IterationStatus.COMPLETED
    ) -> Optional[IssueIteration]:
        """Mark iteration as completed."""
        with self.get_session() as db:
            iteration = db.query(IssueIteration).filter(
                IssueIteration.id == iteration_id
            ).first()
            
            if not iteration:
                return None
            
            iteration.status = status
            iteration.completed_at = datetime.utcnow()
            iteration.updated_at = datetime.utcnow()
            iteration.is_active = False  # Mark as inactive when completed
            
            db.commit()
            db.refresh(iteration)
            return iteration
    
    def get_iteration_by_pr(
        self, 
        repo_full_name: str, 
        pr_number: int
    ) -> Optional[IssueIteration]:
        """Get iteration by PR number."""
        with self.get_session() as db:
            return db.query(IssueIteration).filter(
                IssueIteration.repo_full_name == repo_full_name,
                IssueIteration.pr_number == pr_number,
                IssueIteration.is_active == True
            ).first()
    
    def get_all_active_iterations(self) -> list[IssueIteration]:
        """Get all active iterations."""
        with self.get_session() as db:
            return db.query(IssueIteration).filter(
                IssueIteration.is_active == True,
                IssueIteration.status.in_([
                    IterationStatus.RUNNING,
                    IterationStatus.WAITING_CI,
                    IterationStatus.REVIEWING
                ])
            ).all()


# Global database manager instance
db_manager = DatabaseManager()
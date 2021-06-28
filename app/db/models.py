from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, JSON
from sqlalchemy.orm import relationship

from .database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    users = relationship("User", back_populates="company")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    company = relationship("Company", back_populates="users")


class Agent(Base):
    __tablename__ = 'agents'

    id = Column(String, primary_key=True, index=True)
    did = Column(String, unique=True, index=True)
    verkey = Column(String, index=True)
    metadata = Column(JSON)

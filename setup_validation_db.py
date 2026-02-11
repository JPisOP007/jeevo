#!/usr/bin/env python3
"""
Setup script to initialize validation database with medical data
Run this ONCE before using the validation system
"""

import asyncio
import sys
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.base import Base
from app.database.models import MedicalSource, MedicalCondition
from app.services.medical_source_loader import MedicalSourceLoader
from app.database.repositories import (
    MedicalSourceRepository,
    MedicalConditionRepository,
    MedicalFactRepository,
)


async def setup_database():
    """Initialize the validation database"""
    print("🔧 Setting up Medical Validation Database...\n")
    
    # Use file-based SQLite for testing, or PostgreSQL for production
    db_url = "sqlite+aiosqlite:///./validation_db.sqlite"
    
    print(f"📍 Database URL: {db_url}\n")
    
    # Create engine
    engine = create_async_engine(db_url, echo=False)
    
    # Create tables
    print("📋 Creating database schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Schema created\n")
    
    # Create session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    #  Load data
    print("📚 Loading medical sources...")
    async with async_session() as session:
        try:
            # Load all medical data
            result = await MedicalSourceLoader.load_all(session)
            if result:
                print("✅ Medical sources loaded")
            else:
                print("⚠️  Some sources failed to load, but continuing...")
            
            # Verify sources
            sources = await MedicalSourceRepository.get_active_sources(session)
            print(f"✅ Verified {len(sources)} sources in database:\n")
            for source in sources:
                print(f"   • {source.name} (Authority: {source.authority_level})")
            
            # Verify conditions
            condition_names = [
                "Fever", "Cough", "Diarrhea", "Headache", 
                "Malaria", "Dengue Fever", "Typhoid Fever", "Tuberculosis",
                "Hypertension", "Diabetes"
            ]
            conditions = [
                await MedicalConditionRepository.get_by_name(session, name)
                for name in condition_names
            ]
            conditions = [c for c in conditions if c]
            print(f"\n✅ Verified {len(conditions)} conditions in database")
            for cond in conditions:
                print(f"   • {cond.name} ({len(cond.symptoms or [])} symptoms)")
            
            # Commit everything
            await session.commit()
            print(f"\n✅ Database setup complete!\n")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Error during setup: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    await engine.dispose()
    return True


if __name__ == "__main__":
    print("\n" + "="*80)
    print("  MEDICAL VALIDATION DATABASE SETUP")
    print("="*80 + "\n")
    
    success = asyncio.run(setup_database())
    
    if success:
        print("🎉 Setup complete! You can now run the tests.")
        print("\nTo use in production:")
        print('  1. Set DATABASE_URL="postgresql+asyncpg://..."')
        print("  2. Run this setup script")
        print("  3. Restart the application")
    else:
        print("❌ Setup failed. Check the errors above.")
        sys.exit(1)

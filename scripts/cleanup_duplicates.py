#!/usr/bin/env python
"""
Cleanup Script for Duplicate Predictions
==========================================
Run this script to remove duplicate predictions from the database.
Keeps the oldest prediction for each disease per user per hour.

Usage:
    python cleanup_duplicates.py
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path

# Database path
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / 'app.db'

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def count_duplicates():
    """Count duplicate predictions"""
    with get_db() as conn:
        result = conn.execute('''
            SELECT COUNT(*) as dup_count
            FROM predictions p1
            WHERE EXISTS (
                SELECT 1 FROM predictions p2
                WHERE p1.user_id = p2.user_id
                AND p1.disease = p2.disease
                AND DATE(p1.date) = DATE(p2.date)
                AND p1.id > p2.id
            )
        ''').fetchone()
    return result['dup_count']

def show_duplicates():
    """Show all predicted duplicates"""
    with get_db() as conn:
        duplicates = conn.execute('''
            SELECT 
                p1.id,
                p1.user_id,
                p1.disease,
                p1.confidence,
                DATE(p1.date) as date,
                'WILL DELETE' as status
            FROM predictions p1
            WHERE EXISTS (
                SELECT 1 FROM predictions p2
                WHERE p1.user_id = p2.user_id
                AND p1.disease = p2.disease
                AND DATE(p1.date) = DATE(p2.date)
                AND p1.id > p2.id
            )
            ORDER BY p1.user_id, p1.disease, p1.date DESC
        ''').fetchall()
    
    return duplicates

def cleanup_duplicates():
    """Remove duplicate predictions, keeping oldest per disease per day"""
    
    print("=" * 70)
    print("DUPLICATE PREDICTIONS CLEANUP TOOL")
    print("=" * 70)
    print()
    
    # Count before
    dup_count = count_duplicates()
    print(f"Found {dup_count} duplicate predictions\n")
    
    if dup_count == 0:
        print("✅ No duplicates found! Database is clean.")
        return
    
    # Show duplicates that will be deleted
    print("Predictions that will be DELETED:")
    print("-" * 70)
    duplicates = show_duplicates()
    
    for dup in duplicates:
        print(f"ID: {dup['id']:4} | User: {dup['user_id']:3} | Disease: {dup['disease']:25} | {dup['date']} | Conf: {dup['confidence']}%")
    
    print()
    print(f"Total: {len(duplicates)} predictions will be deleted")
    print()
    
    # Confirm
    response = input("⚠️  Are you sure you want to DELETE these duplicates? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("❌ Cleanup cancelled.")
        return
    
    # Perform cleanup
    try:
        with get_db() as conn:
            # Delete newer duplicates, keep oldest
            deleted = conn.execute('''
                DELETE FROM predictions
                WHERE id IN (
                    SELECT p1.id
                    FROM predictions p1
                    WHERE EXISTS (
                        SELECT 1 FROM predictions p2
                        WHERE p1.user_id = p2.user_id
                        AND p1.disease = p2.disease
                        AND DATE(p1.date) = DATE(p2.date)
                        AND p1.id > p2.id
                    )
                )
            ''')
            conn.commit()
            
        print(f"\n✅ Successfully deleted {deleted.rowcount} duplicate predictions!")
        
        # Verify
        remaining = count_duplicates()
        print(f"✅ Remaining duplicates: {remaining}")
        
    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        return False
    
    return True

def generate_report():
    """Generate duplicate report"""
    print("\n" + "=" * 70)
    print("DUPLICATE PREDICTION REPORT")
    print("=" * 70)
    print()
    
    with get_db() as conn:
        # By user
        by_user = conn.execute('''
            SELECT 
                user_id,
                COUNT(*) as prediction_count,
                COUNT(DISTINCT disease) as unique_diseases
            FROM predictions
            GROUP BY user_id
            ORDER BY prediction_count DESC
        ''').fetchall()
        
        print("Predictions by User:")
        for row in by_user:
            print(f"  User {row['user_id']:3}: {row['prediction_count']:3} predictions ({row['unique_diseases']} diseases)")
        
        print()
        
        # By disease
        by_disease = conn.execute('''
            SELECT 
                disease,
                COUNT(*) as count
            FROM predictions
            GROUP BY disease
            ORDER BY count DESC
        ''').fetchall()
        
        print("Predictions by Disease:")
        for row in by_disease:
            print(f"  {row['disease']:25}: {row['count']:3} predictions")

if __name__ == '__main__':
    if not DB_PATH.exists():
        print(f"❌ Database not found at {DB_PATH}")
        exit(1)
    
    try:
        cleanup_duplicates()
        generate_report()
    except Exception as e:
        print(f"❌ Error: {e}")
        exit(1)

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import psycopg2
from psycopg2.extras import Json, RealDictCursor
import json
from datetime import datetime
from typing import Dict, List, Optional

class AlloyDB:
    def __init__(self, config: Dict):
        self.config = config
        self.conn = None
        self.cursor = None
        self.connect()
    
    def connect(self):
        try:
            self.conn = psycopg2.connect(
                host=self.config['host'],
                port=self.config['port'],
                database=self.config['database'],
                user=self.config['user'],
                password=self.config['password'],
                options=f"-c search_path={self.config['schema']}"
            )
            self.conn.autocommit = False
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            print(f"Connected to database: {self.config['database']}")
        except Exception as e:
            print(f"Connection failed: {e}")
            raise
    
    def commit(self):
        self.conn.commit()
    
    def rollback(self):
        self.conn.rollback()
    
    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
    
    def add_sample(self, sample_id: str, composition: Dict, 
                   material_class: str, source_type: str = 'experimental',
                   mass_grams: float = None, parent_sample_id: str = None,
                   notes: str = None, vec: float = None, delta: float = None,
                   delta_h_mix: float = None) -> int:
        parent_id = None
        if parent_sample_id:
            self.cursor.execute(
                "SELECT id FROM samples WHERE sample_id = %s",
                (parent_sample_id,)
            )
            result = self.cursor.fetchone()
            if result:
                parent_id = result['id']
        
        query = """
            INSERT INTO samples (
                sample_id, composition, material_class_id, 
                mass_grams, source_type, parent_sample_id, notes,
                vec, delta, delta_h_mix
            )
            VALUES (
                %s, %s, 
                (SELECT id FROM material_classes WHERE class_name = %s),
                %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id
        """
        self.cursor.execute(query, (
            sample_id, Json(composition), material_class,
            mass_grams, source_type, parent_id, notes,
            vec, delta, delta_h_mix
        ))
        self.commit()
        sample_db_id = self.cursor.fetchone()['id']
        print(f"Added sample: {sample_id} (ID: {sample_db_id})")
        return sample_db_id
    
    def get_sample(self, sample_id: str) -> Optional[Dict]:
        query = """
            SELECT 
                s.*,
                mc.class_name as material_class,
                s2.sample_id as parent_sample
            FROM samples s
            LEFT JOIN material_classes mc ON s.material_class_id = mc.id
            LEFT JOIN samples s2 ON s.parent_sample_id = s2.id
            WHERE s.sample_id = %s
        """
        self.cursor.execute(query, (sample_id,))
        return self.cursor.fetchone()
    
    def get_all_samples(self, limit: int = 50) -> List[Dict]:
        query = """
            SELECT 
                s.sample_id,
                s.composition,
                mc.class_name as material_class,
                s.source_type,
                s.created_at,
                s.notes
            FROM samples s
            JOIN material_classes mc ON s.material_class_id = mc.id
            ORDER BY s.created_at DESC
            LIMIT %s
        """
        self.cursor.execute(query, (limit,))
        return self.cursor.fetchall()
    
    def add_characterization(self, sample_id: str, char_type: str,
                           file_path: str = None, instrument: str = None,
                           parameters: Dict = None, notes: str = None) -> int:
        query = """
            INSERT INTO characterization (
                sample_id, char_type, instrument,
                file_path, parameters, notes
            )
            VALUES (
                (SELECT id FROM samples WHERE sample_id = %s),
                %s, %s, %s, %s, %s
            )
            RETURNING id
        """
        self.cursor.execute(query, (
            sample_id, char_type, instrument,
            file_path, Json(parameters or {}), notes
        ))
        self.commit()
        char_id = self.cursor.fetchone()['id']
        print(f"Added characterization (ID: {char_id}) for {sample_id}")
        return char_id
    
    def add_property(self, characterization_id: int, property_name: str,
                    property_value: float, property_unit: str,
                    confidence_score: float = 0.7) -> int:
        query = """
            INSERT INTO properties (
                characterization_id, property_name, 
                property_value, property_unit, confidence_score
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        self.cursor.execute(query, (
            characterization_id, property_name,
            property_value, property_unit, confidence_score
        ))
        self.commit()
        prop_id = self.cursor.fetchone()['id']
        print(f"Added property: {property_name} = {property_value} {property_unit}")
        return prop_id
    
    def get_properties(self, sample_id: str) -> List[Dict]:
        query = """
            SELECT 
                p.property_name,
                p.property_value,
                p.property_unit,
                c.char_type,
                c.created_at
            FROM properties p
            JOIN characterization c ON p.characterization_id = c.id
            WHERE c.sample_id = (SELECT id FROM samples WHERE sample_id = %s)
            ORDER BY c.created_at DESC
        """
        self.cursor.execute(query, (sample_id,))
        return self.cursor.fetchall()
    
    def add_synthesis(self, sample_id: str, method: str,
                     temperature: float = None, atmosphere: str = None,
                     duration_minutes: float = None, success: bool = None,
                     notes: str = None) -> int:
        query = """
            INSERT INTO synthesis (
                sample_id, method, temperature,
                atmosphere, duration_minutes, success, notes
            )
            VALUES (
                (SELECT id FROM samples WHERE sample_id = %s),
                %s, %s, %s, %s, %s, %s
            )
            RETURNING id
        """
        self.cursor.execute(query, (
            sample_id, method, temperature,
            atmosphere, duration_minutes, success, notes
        ))
        self.commit()
        syn_id = self.cursor.fetchone()['id']
        print(f"Added synthesis record (ID: {syn_id}) for {sample_id}")
        return syn_id
    
    def add_literature_check(self, sample_db_id: int, source_db: str, tier: int,
                            match_formula: str = None, match_id: str = None,
                            stability: float = None, experimentally_known: bool = None,
                            composition_distance: float = None) -> int:
        query = """
            INSERT INTO literature_checks (
                sample_id, source_db, tier, match_formula, match_id,
                stability, experimentally_known, composition_distance
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        self.cursor.execute(query, (
            sample_db_id, source_db, tier, match_formula, match_id,
            stability, experimentally_known, composition_distance
        ))
        self.commit()
        check_id = self.cursor.fetchone()['id']
        print(f"  Logged {source_db} tier {tier}: {match_formula}")
        return check_id

    def get_family_tree(self, sample_id: str) -> List[Dict]:
        query = """
            WITH RECURSIVE family AS (
                SELECT id, sample_id, parent_sample_id
                FROM samples
                WHERE sample_id = %s
                UNION
                SELECT s.id, s.sample_id, s.parent_sample_id
                FROM samples s
                JOIN family f ON s.parent_sample_id = f.id
            )
            SELECT sample_id, parent_sample_id
            FROM family
            WHERE sample_id != %s
        """
        self.cursor.execute(query, (sample_id, sample_id))
        return self.cursor.fetchall()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

def get_db():
    from db_config import DB_CONFIG
    return AlloyDB(DB_CONFIG)

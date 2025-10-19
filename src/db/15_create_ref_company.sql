-- ref_company.sql
-- Static reference data for Torn company types and their benefits

DROP TABLE IF EXISTS ref_company;

CREATE TABLE ref_company (
    id SERIAL PRIMARY KEY,
    company_type INTEGER NOT NULL,         -- e.g., 23 = Music Store, 10 = Adult Novelty Store
    company_class TEXT NOT NULL,           -- Human-readable company type name
    rating INTEGER NOT NULL,               -- Rating level that unlocks this benefit
    benefit_description TEXT NOT NULL      -- Description of the benefit
);

-- RLS
ALTER TABLE ref_company ENABLE ROW LEVEL SECURITY;

-- =========================
-- Adult Novelty Store (type 10)
-- =========================
INSERT INTO ref_company (company_type, company_class, rating, benefit_description) VALUES
(10, 'Adult Novelty Store', 1, 'Blackmail: 1 Job Point for money'),
(10, 'Adult Novelty Store', 3, 'Voyeur: 20 Job points for eDVD'),
(10, 'Adult Novelty Store', 5, 'Party Supplies: 500 Job points for a pack of Trojans'),
(10, 'Adult Novelty Store', 7, 'Bondage: 25% enemy speed reduction'),
(10, 'Adult Novelty Store', 10, 'Indecent: 100% happy gain from eDVD ');


-- =========================
-- Music Store (type 23)
-- =========================
INSERT INTO ref_company (company_type, company_class, rating, benefit_description) VALUES
(23, 'Music Store', 1, 'Ambience: 1 Job point for 50 happiness'),
(23, 'Music Store', 3, 'Well Tuned: +30% gym experience gain.'),
(23, 'Music Store', 5, 'High Fidelity: Reduces opponent stealth by 2.0.'),
(23, 'Music Store', 7, 'Deafened: 10 Job points for maximum stealth'),
(23, 'Music Store', 10, 'The Score: +15% passive battle stats.');


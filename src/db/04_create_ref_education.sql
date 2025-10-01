-- Tracks which stock blocks a director currently holds
CREATE TABLE ref_education (
    id BIGSERIAL PRIMARY KEY,
    course_id INT NOT NULL,
    course_code TEXT NOT NULL,
    course_name TEXT NOT NULL,
    course_effect TEXT NOT NULL,
    course_duration INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE,
    UNIQUE (course_id)
);

-- RLS
ALTER TABLE ref_education ENABLE ROW LEVEL SECURITY;

-- Hard coded data, this shouldnt change often enough to warrant a Lambda function and were only after a subset of all education courses

INSERT INTO ref_education (course_id, course_code, course_name, course_effect, course_duration, updated_at)
VALUES
  (1, 'BUS1100', 'Introduction to Business', 'None', 604800, now()),
  (2, 'BUS2200', 'Statistics', 'Gain 2% productivity for your company', 1209600, now()),
  (3, 'BUS2300', 'Communication', 'Gain 5% employee effectiveness for your company', 1209600, now()),
  (4, 'BUS2400', 'Marketing', 'Gain an increase in advertising effectiveness for your company', 1814400, now()),
  (5, 'BUS2500', 'Corporate Finance', 'Gain 2% productivity for your company', 1209600, now()),
  (6, 'BUS2600', 'Corporate Strategy', 'Gain 7% employee effectiveness for your company', 2419200, now()),
  (7, 'BUS2700', 'Pricing Strategy', 'Gain 10% perceived product value for your company', 2419200, now()),
  (8, 'BUS2800', 'Logistics', 'Gain 2% productivity for your company', 1209600, now()),
  (9, 'BUS2900', 'Product Management', 'Gain 5% perceived product value for your company', 1814400, now()),
  (10, 'BUS2100', 'Business Ethics', 'Gain 2% productivity for your company', 1814400, now()),
  (11, 'BUS2110', 'Human Resource Management', 'Gain a passive bonus to employee working stats in your company', 1814400, now()),
  (12, 'BUS2120', 'E-Commerce', 'Gain 2% productivity for your company', 1814400, now()),
  (13, 'BUS3130', 'Bachelor of Commerce', 'Unlock new size, storage size & staff room upgrades for your company', 3024000, now()),
  (22, 'MTH1220', 'Introduction to Mathematics', 'None', 604800, now()),
  (28, 'MTH2280', 'Probability', 'Gain 1% productivity for your company', 1814400, now()),
  (88, 'LAW1880', 'Introduction to Law', 'None', 604800, now()),
  (100, 'LAW2100', 'Media Law', 'Gain an increase in advertising effectiveness for your company', 1814400, now())

ON CONFLICT (course_id) 
DO UPDATE SET
  updated_at = now();
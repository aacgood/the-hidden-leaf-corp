-- Aliases
-- d  = director table
-- de = director_education table
-- re = ref_education table

SELECT
    d.torn_user_id,
    d.director_name,
    de.course_id,
    re.course_name,
    re.course_effect,
    de.completed,
    de.updated_at
FROM
    directors d
LEFT JOIN
    director_education de
    ON d.torn_user_id = de.torn_user_id
LEFT JOIN
    ref_education re
    ON de.course_id = re.course_id
ORDER BY
    d.torn_user_id,
    de.course_id;

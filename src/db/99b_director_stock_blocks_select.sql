-- Aliases
-- d  = director table
-- rs = ref_stocks table
-- dsb = director_stock_blocks table

SELECT d.torn_user_id,
       d.director_name,
       rs.stock_id,
       rs.stock_acronym,
       rs.stock_name,
       rs.stock_requirement,
       rs.stock_effect,
       dsb.shares_held,
       dsb.has_block,
       dsb.updated_at
FROM directors d
JOIN director_stock_blocks dsb 
  ON d.torn_user_id = dsb.torn_user_id
JOIN ref_stocks rs 
  ON dsb.stock_id = rs.stock_id;

SELECT 
    tg.tgname AS trigger_name,
    tbl.relname AS table_name,
    ns.nspname AS schema_name,
    p.proname AS function_name,
    tgenabled AS enabled
FROM pg_trigger tg
JOIN pg_class tbl ON tg.tgrelid = tbl.oid
JOIN pg_namespace ns ON tbl.relnamespace = ns.oid
JOIN pg_proc p ON tg.tgfoid = p.oid
WHERE NOT tg.tgisinternal
ORDER BY tbl.relname;

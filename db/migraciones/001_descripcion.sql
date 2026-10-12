-- Agrega la columna de metodología a las series (correr una sola vez en Supabase → SQL Editor)
alter table series add column if not exists descripcion text;

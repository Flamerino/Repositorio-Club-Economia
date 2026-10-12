-- Esquema de la base del Club de Economía (Supabase / Postgres)
-- Pegar completo en Supabase → SQL Editor → Run

create table if not exists series (
    id              text primary key,          -- ej: bcra_api_74, bcra_itcrm
    nombre          text not null,
    fuente          text not null,             -- BCRA, INDEC, MECON...
    categoria       text,                      -- Reservas, Tasas de mercado...
    unidad          text,                      -- Millones de USD, %, Índice...
    frecuencia      text,                      -- D, M, T, A
    id_api_bcra     integer,                   -- IdVariable en api.bcra.gob.ar (si tiene)
    archivo_origen  text,
    descripcion     text,                      -- metodología / cómo se construye
    actualizado     timestamptz default now()
);

create table if not exists observaciones (
    serie_id  text not null references series(id) on delete cascade,
    fecha     date not null,
    valor     double precision not null,
    primary key (serie_id, fecha)
);

-- Lectura pública (la página usa la clave "anon"); la escritura queda
-- reservada a la clave service_role, que solo usa GitHub Actions.
alter table series enable row level security;
alter table observaciones enable row level security;

drop policy if exists "lectura publica series" on series;
create policy "lectura publica series" on series for select using (true);

drop policy if exists "lectura publica observaciones" on observaciones;
create policy "lectura publica observaciones" on observaciones for select using (true);

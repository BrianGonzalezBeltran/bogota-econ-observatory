-- Bogotá Economic Observatory — Dimensional Model
-- Auto-executed on first PostgreSQL container start

-- ============================================================
-- DIMENSION TABLES
-- ============================================================

CREATE TABLE dim_time (
    time_id         SERIAL PRIMARY KEY,
    year            SMALLINT NOT NULL,
    quarter         SMALLINT,          -- 1-4 (for PIB, mercado laboral)
    month           SMALLINT,          -- 1-12 (for dinámica empresarial)
    trimester_label TEXT,              -- "Enero - Marzo" etc. (mercado laboral)
    UNIQUE (year, quarter, month)
);

CREATE TABLE dim_locality (
    locality_id   SERIAL PRIMARY KEY,
    locality_code SMALLINT NOT NULL UNIQUE,
    locality_name TEXT NOT NULL
);

CREATE TABLE dim_economic_sector (
    sector_id          SERIAL PRIMARY KEY,
    rama_name          TEXT,                 -- "Comercio", "Industria", etc.
    ciiu_code          VARCHAR(50),          -- CIIU Rev. 4 code or synthetic PIB_ prefix
    ciiu_description   TEXT,                 -- Full CIIU description
    UNIQUE (ciiu_code)
);

CREATE TABLE dim_company_size (
    size_id   SERIAL PRIMARY KEY,
    size_code VARCHAR(5) NOT NULL UNIQUE,
    size_name TEXT NOT NULL                  -- "Microempresa", "Pequeña", etc.
);

CREATE TABLE dim_legal_form (
    legal_form_id   SERIAL PRIMARY KEY,
    legal_form_code VARCHAR(5) NOT NULL UNIQUE,
    legal_form_name TEXT NOT NULL            -- "Persona Natural", "SAS", etc.
);

-- ============================================================
-- FACT TABLES
-- ============================================================

CREATE TABLE fact_business_dynamics (
    id                    SERIAL PRIMARY KEY,
    time_id               INT NOT NULL REFERENCES dim_time(time_id),
    locality_id           INT NOT NULL REFERENCES dim_locality(locality_id),
    sector_id             INT NOT NULL REFERENCES dim_economic_sector(sector_id),
    size_id               INT NOT NULL REFERENCES dim_company_size(size_id),
    legal_form_id         INT NOT NULL REFERENCES dim_legal_form(legal_form_id),
    gender_legal_rep      VARCHAR(20),       -- "Masculino", "Femenino", "Indeterminado"
    empresas_vigentes     INT DEFAULT 0,
    empresas_creadas      INT DEFAULT 0,
    empresas_canceladas   INT DEFAULT 0
);

CREATE TABLE fact_labor_market (
    id                                  SERIAL PRIMARY KEY,
    time_id                             INT NOT NULL REFERENCES dim_time(time_id),
    poblacion_total                     FLOAT,
    poblacion_edad_trabajar             FLOAT,
    fuerza_trabajo                      FLOAT,
    ocupados                            FLOAT,
    desocupados                         FLOAT,
    poblacion_fuera_fuerza_laboral      FLOAT,
    subocupados                         FLOAT,
    fuerza_trabajo_potencial            FLOAT,
    ocupados_asalariados                FLOAT,
    ocupados_no_asalariados             FLOAT,
    total_informales                    FLOAT,
    tasa_global_participacion           FLOAT,
    tasa_ocupacion                      FLOAT,
    tasa_desocupacion                   FLOAT,
    tasa_subocupados                    FLOAT,
    tasa_asalariados                    FLOAT,
    tasa_no_asalariados                 FLOAT,
    tasa_inactividad                    FLOAT,
    tasa_informalidad                   FLOAT
);

CREATE TABLE fact_gdp (
    id                                      SERIAL PRIMARY KEY,
    time_id                                 INT NOT NULL REFERENCES dim_time(time_id),
    sector_id                               INT REFERENCES dim_economic_sector(sector_id),
    pib_precios_corrientes                  FLOAT,
    pib_precios_constantes_2015             FLOAT,
    variacion_anual_constantes              FLOAT,
    variacion_trimestral_constantes         FLOAT,
    variacion_anual_corrientes              FLOAT,
    variacion_trimestral_corrientes         FLOAT
);

-- ============================================================
-- INDEXES for common query patterns
-- ============================================================

CREATE INDEX idx_fbd_time ON fact_business_dynamics(time_id);
CREATE INDEX idx_fbd_locality ON fact_business_dynamics(locality_id);
CREATE INDEX idx_fbd_sector ON fact_business_dynamics(sector_id);
CREATE INDEX idx_fbd_size ON fact_business_dynamics(size_id);
CREATE INDEX idx_flm_time ON fact_labor_market(time_id);
CREATE INDEX idx_fgdp_time ON fact_gdp(time_id);
CREATE INDEX idx_fgdp_sector ON fact_gdp(sector_id);

-- Additive, Zero-Data-Loss Supabase Postgres Optimizations & RPC Functions
-- All statements are idempotent (CREATE EXTENSION IF NOT EXISTS, CREATE INDEX IF NOT EXISTS,
-- CREATE OR REPLACE FUNCTION, CREATE MATERIALIZED VIEW IF NOT EXISTS).
-- Zero DROP / TRUNCATE / DELETE of canonical user or market rows.

-- 1. Native Supabase extensions in dedicated extensions schema
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA extensions;
EXCEPTION WHEN OTHERS THEN
    NULL;
END $$;

DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;
EXCEPTION WHEN OTHERS THEN
    NULL;
END $$;

-- 2. Covering & composite indexes for hot point-in-time queries
CREATE INDEX IF NOT EXISTS idx_prices_asset_status_date_desc
    ON public.prices (asset_id, status, observation_date DESC)
    INCLUDE (raw_close, adjusted_close, adjustment_factor, volume, source);

CREATE INDEX IF NOT EXISTS idx_data_lineages_table_record_created
    ON public.data_lineages (record_table, record_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_fin_stmt_pit
    ON public.financial_statements (symbol, status, publication_date DESC, fiscal_period_end DESC);

CREATE INDEX IF NOT EXISTS idx_macro_obs_series_date
    ON public.macro_observations (series_id, observation_date DESC);

CREATE INDEX IF NOT EXISTS idx_events_as_of_date
    ON public.events (as_of_date DESC, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_norm_income_sym_period
    ON public.normalized_income (symbol, fiscal_period_end DESC);

CREATE INDEX IF NOT EXISTS idx_norm_bs_sym_period
    ON public.normalized_balance_sheets (symbol, fiscal_period_end DESC);

CREATE INDEX IF NOT EXISTS idx_norm_cf_sym_period
    ON public.normalized_cash_flows (symbol, fiscal_period_end DESC);

CREATE INDEX IF NOT EXISTS idx_fund_metrics_sym_metric_date
    ON public.fundamental_metrics (symbol, metric_id, fiscal_period_end DESC);

CREATE INDEX IF NOT EXISTS idx_corp_actions_sym_ex
    ON public.corporate_actions (symbol, action_date DESC);

CREATE INDEX IF NOT EXISTS idx_index_memberships_idx_sym
    ON public.index_memberships (index_symbol, is_active, symbol);

-- 3. Native full-text + trigram + pgvector columns on document_chunks for hybrid RAG
DO $$
BEGIN
    ALTER TABLE public.document_chunks
        ADD COLUMN IF NOT EXISTS search_tsv tsvector
        GENERATED ALWAYS AS (
            to_tsvector('simple', coalesce(section, '') || ' ' || coalesce(text, ''))
        ) STORED;
EXCEPTION WHEN OTHERS THEN
    NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_doc_chunks_tsv
    ON public.document_chunks USING GIN (search_tsv);

DO $$
BEGIN
    CREATE INDEX IF NOT EXISTS idx_doc_chunks_trgm
        ON public.document_chunks USING GIN (text extensions.gin_trgm_ops);
EXCEPTION WHEN OTHERS THEN
    NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE public.document_chunks
        ADD COLUMN IF NOT EXISTS embedding_vec extensions.vector(768);
    CREATE INDEX IF NOT EXISTS idx_doc_chunks_embedding_hnsw
        ON public.document_chunks USING hnsw (embedding_vec extensions.vector_cosine_ops);
EXCEPTION WHEN OTHERS THEN
    NULL;
END $$;

-- 4. Materialized View for Screener & Valuation fast reads
CREATE MATERIALIZED VIEW IF NOT EXISTS public.mv_daily_screener_metrics AS
WITH latest_prices AS (
    SELECT DISTINCT ON (p.asset_id)
        p.asset_id,
        COALESCE(p.adjusted_close, p.raw_close)::double precision AS current_price,
        p.observation_date AS price_date,
        p.source AS price_source
    FROM public.prices p
    WHERE p.status = 'VALID'
      AND p.observation_date <= CURRENT_DATE
    ORDER BY p.asset_id, p.observation_date DESC
),
latest_shares AS (
    SELECT DISTINCT ON (upper(fm.symbol))
        upper(fm.symbol) AS symbol,
        fm.value::double precision AS shares_outstanding
    FROM public.fundamental_metrics fm
    WHERE fm.metric_id IN ('OUTSTANDING_SHARES', 'TOTAL_SHARES', 'LISTED_SHARES')
      AND fm.value IS NOT NULL
      AND fm.value > 0
    ORDER BY upper(fm.symbol), fm.fiscal_period_end DESC,
             CASE fm.metric_id WHEN 'OUTSTANDING_SHARES' THEN 1 WHEN 'TOTAL_SHARES' THEN 2 ELSE 3 END
),
ranked_q_inc AS (
    SELECT
        upper(ni.symbol) AS symbol,
        ni.fiscal_period_end,
        ni.revenue::double precision AS revenue,
        ni.gross_profit::double precision AS gross_profit,
        COALESCE(ni.net_income_parent, ni.net_income)::double precision AS net_income_parent,
        ni.eps_basic::double precision AS eps_basic,
        ni.shares_basic::double precision AS shares_basic,
        ROW_NUMBER() OVER (PARTITION BY upper(ni.symbol), ni.fiscal_period_end ORDER BY fs.version DESC, ni.id DESC) AS dedup_rn
    FROM public.normalized_income ni
    JOIN public.financial_statements fs ON fs.id = ni.statement_id
    WHERE fs.status = 'VALID'
      AND fs.statement_type = 'INCOME_STATEMENT'
      AND ni.period_type = 'QUARTERLY'
      AND fs.publication_date <= CURRENT_DATE
),
q4_ttm AS (
    SELECT
        symbol,
        COUNT(*) AS q_count,
        MAX(fiscal_period_end) AS latest_q_end,
        SUM(revenue) AS rev_ttm,
        SUM(gross_profit) AS gp_ttm,
        SUM(net_income_parent) AS ni_ttm,
        MAX(shares_basic) FILTER (WHERE rn = 1) AS q_shares
    FROM (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY fiscal_period_end DESC) AS rn
        FROM ranked_q_inc
        WHERE dedup_rn = 1
    ) t
    WHERE rn <= 4
    GROUP BY symbol
),
latest_a_inc AS (
    SELECT DISTINCT ON (upper(ni.symbol))
        upper(ni.symbol) AS symbol,
        ni.fiscal_period_end AS latest_a_end,
        ni.revenue::double precision AS rev_a,
        ni.gross_profit::double precision AS gp_a,
        COALESCE(ni.net_income_parent, ni.net_income)::double precision AS ni_a,
        ni.eps_basic::double precision AS eps_a,
        ni.shares_basic::double precision AS a_shares
    FROM public.normalized_income ni
    JOIN public.financial_statements fs ON fs.id = ni.statement_id
    WHERE fs.status = 'VALID'
      AND fs.statement_type = 'INCOME_STATEMENT'
      AND ni.period_type = 'ANNUAL'
      AND fs.publication_date <= CURRENT_DATE
    ORDER BY upper(ni.symbol), ni.fiscal_period_end DESC, fs.version DESC, ni.id DESC
),
latest_bs AS (
    SELECT DISTINCT ON (upper(nb.symbol))
        upper(nb.symbol) AS symbol,
        nb.fiscal_period_end AS bs_end,
        COALESCE(nb.equity_parent, nb.total_equity)::double precision AS total_equity,
        (COALESCE(nb.short_term_debt, 0) + COALESCE(nb.long_term_debt, 0))::double precision AS gross_debt,
        nb.total_current_assets::double precision AS total_current_assets,
        nb.total_current_liabilities::double precision AS total_current_liabilities
    FROM public.normalized_balance_sheets nb
    JOIN public.financial_statements fs ON fs.id = nb.statement_id
    WHERE fs.status = 'VALID'
      AND fs.statement_type = 'BALANCE_SHEET'
      AND nb.period_type IN ('QUARTERLY', 'ANNUAL')
      AND COALESCE(nb.equity_parent, nb.total_equity) IS NOT NULL
      AND fs.publication_date <= CURRENT_DATE
    ORDER BY upper(nb.symbol), nb.fiscal_period_end DESC, fs.version DESC, nb.id DESC
),
idx_flags AS (
    SELECT
        upper(im.symbol) AS symbol,
        bool_or(im.index_symbol = 'VN30' AND im.is_active) AS is_vn30,
        bool_or(im.index_symbol = 'VN100' AND im.is_active) AS is_vn100
    FROM public.index_memberships im
    GROUP BY upper(im.symbol)
),
base AS (
    SELECT
        upper(a.symbol) AS symbol,
        COALESCE(a.name, upper(a.symbol) || ' Corporation') AS name,
        upper(COALESCE(NULLIF(trim(a.sector), ''), 'GENERAL')) AS raw_sector,
        a.asset_type,
        lp.current_price,
        lp.price_date,
        lp.price_source,
        COALESCE(ls.shares_outstanding, q4.q_shares, la.a_shares) AS shares_outstanding,
        CASE WHEN COALESCE(q4.q_count, 0) >= 4 THEN q4.rev_ttm ELSE la.rev_a END AS revenue_ttm,
        CASE WHEN COALESCE(q4.q_count, 0) >= 4 THEN q4.gp_ttm ELSE la.gp_a END AS gross_profit_ttm,
        CASE WHEN COALESCE(q4.q_count, 0) >= 4 THEN q4.ni_ttm ELSE la.ni_a END AS net_income_ttm,
        la.eps_a,
        COALESCE(q4.latest_q_end, la.latest_a_end) AS latest_fiscal_end,
        lbs.total_equity,
        lbs.gross_debt,
        lbs.total_current_assets,
        lbs.total_current_liabilities,
        COALESCE(idx.is_vn30, false) AS is_vn30,
        COALESCE(idx.is_vn100, false) AS is_vn100
    FROM public.assets a
    LEFT JOIN latest_prices lp ON lp.asset_id = a.id
    LEFT JOIN latest_shares ls ON ls.symbol = upper(a.symbol)
    LEFT JOIN q4_ttm q4 ON q4.symbol = upper(a.symbol)
    LEFT JOIN latest_a_inc la ON la.symbol = upper(a.symbol)
    LEFT JOIN latest_bs lbs ON lbs.symbol = upper(a.symbol)
    LEFT JOIN idx_flags idx ON idx.symbol = upper(a.symbol)
    WHERE a.status = 'ACTIVE'
      AND upper(COALESCE(a.asset_type, 'STOCK')) NOT IN ('INDEX', 'ETF')
      AND a.symbol NOT LIKE '^%'
      AND COALESCE(q4.latest_q_end, la.latest_a_end) IS NOT NULL
)
SELECT
    symbol,
    name,
    raw_sector AS sector,
    current_price,
    price_date,
    price_source,
    shares_outstanding,
    revenue_ttm,
    net_income_ttm,
    total_equity,
    latest_fiscal_end,
    is_vn30,
    is_vn100,
    CASE WHEN current_price IS NOT NULL AND shares_outstanding IS NOT NULL AND shares_outstanding > 0
         THEN round(((current_price * shares_outstanding) / 1000000000.0)::numeric, 2)::double precision
         ELSE NULL END AS market_cap_billion_vnd,
    CASE WHEN current_price IS NOT NULL AND shares_outstanding IS NOT NULL AND shares_outstanding > 0
              AND net_income_ttm IS NOT NULL AND net_income_ttm > 0
         THEN round((current_price / ((net_income_ttm * 1000000000.0) / shares_outstanding))::numeric, 2)::double precision
         WHEN current_price IS NOT NULL AND eps_a IS NOT NULL AND eps_a > 0
         THEN round((current_price / eps_a)::numeric, 2)::double precision
         ELSE NULL END AS pe,
    CASE WHEN current_price IS NOT NULL AND shares_outstanding IS NOT NULL AND shares_outstanding > 0
              AND total_equity IS NOT NULL AND total_equity > 0
         THEN round((current_price / ((total_equity * 1000000000.0) / shares_outstanding))::numeric, 2)::double precision
         ELSE NULL END AS pb,
    CASE WHEN net_income_ttm IS NOT NULL AND total_equity IS NOT NULL AND total_equity > 0
         THEN round(((net_income_ttm / total_equity) * 100.0)::numeric, 2)::double precision
         ELSE NULL END AS roe,
    CASE WHEN raw_sector IN ('BANK', 'BANKING') THEN NULL
         WHEN gross_profit_ttm IS NOT NULL AND revenue_ttm IS NOT NULL AND revenue_ttm > 0
         THEN round(((gross_profit_ttm / revenue_ttm) * 100.0)::numeric, 2)::double precision
         ELSE NULL END AS gross_margin,
    CASE WHEN net_income_ttm IS NOT NULL AND revenue_ttm IS NOT NULL AND revenue_ttm > 0
         THEN round(((net_income_ttm / revenue_ttm) * 100.0)::numeric, 2)::double precision
         ELSE NULL END AS net_margin,
    CASE WHEN raw_sector IN ('BANK', 'BANKING') THEN NULL
         WHEN gross_debt IS NOT NULL AND total_equity IS NOT NULL AND total_equity > 0
         THEN round((gross_debt / total_equity)::numeric, 4)::double precision
         ELSE NULL END AS de_ratio,
    CASE WHEN raw_sector IN ('BANK', 'BANKING') THEN NULL
         WHEN total_current_assets IS NOT NULL AND total_current_liabilities IS NOT NULL AND total_current_liabilities > 0
         THEN round((total_current_assets / total_current_liabilities)::numeric, 2)::double precision
         ELSE NULL END AS current_ratio
FROM base;

CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_daily_screener_symbol
    ON public.mv_daily_screener_metrics (symbol);

CREATE INDEX IF NOT EXISTS idx_mv_screener_vn30_vn100
    ON public.mv_daily_screener_metrics (is_vn30, is_vn100, sector);

-- 5. Shared internal coverage computation helper (eliminates duplicated SQL logic across RPCs)
CREATE OR REPLACE FUNCTION public._fn_instrument_coverage_rows(
    p_as_of date DEFAULT CURRENT_DATE,
    p_symbol text DEFAULT NULL
)
RETURNS TABLE (
    symbol text,
    name text,
    exchange text,
    asset_type text,
    is_index boolean,
    overall_status text,
    analyst_ready boolean,
    eligible_evidence_count integer,
    missing_datasets jsonb,
    datasets jsonb,
    price_eligible boolean,
    price_status text,
    fund_eligible boolean,
    has_price_row boolean
)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, extensions, pg_temp
AS $$
    WITH recent_events AS (
        SELECT e.title, e.as_of_date, e.impacts::text AS impacts_txt
        FROM public.events e
        WHERE e.as_of_date <= p_as_of
        ORDER BY e.as_of_date DESC
        LIMIT 200
    ),
    target_assets AS (
        SELECT
            a.id,
            upper(a.symbol) AS symbol,
            a.name,
            COALESCE(a.exchange, 'HOSE') AS exchange,
            COALESCE(a.asset_type, 'STOCK') AS asset_type,
            (upper(COALESCE(a.asset_type, 'STOCK')) = 'INDEX') AS is_index
        FROM public.assets a
        WHERE a.status = 'ACTIVE'
          AND (p_symbol IS NULL OR upper(a.symbol) = upper(trim(p_symbol)))
    )
    SELECT
        ta.symbol,
        ta.name,
        ta.exchange,
        ta.asset_type,
        ta.is_index,
        CASE
            WHEN p_info.p_eligible AND (ta.is_index OR f_info.f_eligible) THEN 'AVAILABLE'
            WHEN (
                (CASE WHEN p_info.p_eligible THEN 1 ELSE 0 END)
                + (CASE WHEN (NOT ta.is_index AND upper(ta.asset_type) <> 'ETF' AND f_info.f_eligible) THEN 1 ELSE 0 END)
                + (CASE WHEN (NOT ta.is_index AND upper(ta.asset_type) <> 'ETF' AND p_info.p_status = 'AVAILABLE' AND f_info.f_status = 'AVAILABLE') THEN 1 ELSE 0 END)
                + (CASE WHEN ev_info.total_ev > 0 THEN 1 ELSE 0 END)
            ) > 0 THEN 'PARTIAL'
            ELSE 'INSUFFICIENT_DATA'
        END AS overall_status,
        (
            (p_info.p_eligible AND (ta.is_index OR f_info.f_eligible))
            OR (
                (CASE WHEN p_info.p_eligible THEN 1 ELSE 0 END)
                + (CASE WHEN (NOT ta.is_index AND upper(ta.asset_type) <> 'ETF' AND f_info.f_eligible) THEN 1 ELSE 0 END)
                + (CASE WHEN (NOT ta.is_index AND upper(ta.asset_type) <> 'ETF' AND p_info.p_status = 'AVAILABLE' AND f_info.f_status = 'AVAILABLE') THEN 1 ELSE 0 END)
                + (CASE WHEN ev_info.total_ev > 0 THEN 1 ELSE 0 END)
            ) > 0
        ) AS analyst_ready,
        (
            (CASE WHEN p_info.p_eligible THEN 1 ELSE 0 END)
            + (CASE WHEN (NOT ta.is_index AND upper(ta.asset_type) <> 'ETF' AND f_info.f_eligible) THEN 1 ELSE 0 END)
            + (CASE WHEN (NOT ta.is_index AND upper(ta.asset_type) <> 'ETF' AND p_info.p_status = 'AVAILABLE' AND f_info.f_status = 'AVAILABLE') THEN 1 ELSE 0 END)
            + (CASE WHEN ev_info.total_ev > 0 THEN 1 ELSE 0 END)
        )::integer AS eligible_evidence_count,
        (
            SELECT COALESCE(jsonb_agg(ds_name), '[]'::jsonb)
            FROM (
                SELECT 'prices' AS ds_name WHERE NOT p_info.has_price
                UNION ALL
                SELECT 'fundamentals' WHERE NOT ta.is_index AND upper(ta.asset_type) <> 'ETF' AND (NOT f_info.has_fund OR f_info.f_status = 'INSUFFICIENT_DATA')
                UNION ALL
                SELECT 'valuation' WHERE NOT ta.is_index AND upper(ta.asset_type) <> 'ETF' AND NOT (p_info.p_status = 'AVAILABLE' AND f_info.f_status = 'AVAILABLE')
                UNION ALL
                SELECT 'events' WHERE ev_info.total_ev = 0
            ) m
        ) AS missing_datasets,
        jsonb_build_object(
            'prices', p_info.p_json,
            'fundamentals', f_info.f_json,
            'valuation', v_info.v_json,
            'events', ev_info.e_json
        ) AS datasets,
        p_info.p_eligible AS price_eligible,
        p_info.p_status AS price_status,
        (NOT ta.is_index AND upper(ta.asset_type) <> 'ETF' AND f_info.f_eligible) AS fund_eligible,
        p_info.has_price AS has_price_row
    FROM target_assets ta
    CROSS JOIN LATERAL (
        SELECT
            (agg.cnt > 0) AS has_price,
            CASE
                WHEN agg.cnt = 0 THEN 'INSUFFICIENT_DATA'
                WHEN (p_as_of - latest.observation_date) > 7 THEN 'STALE'
                ELSE 'AVAILABLE'
            END AS p_status,
            (
                agg.cnt > 0
                AND (p_as_of - latest.observation_date) <= 7
                AND (
                    has_lin.exists_lin
                    OR COALESCE(latest.source, '') ~* '(DNSE|LOTUSMARKET|VNDIRECT|VIETCAP|VIETSTOCK|KBS)'
                )
            ) AS p_eligible,
            CASE
                WHEN agg.cnt = 0 THEN jsonb_build_object(
                    'dataset', 'prices',
                    'exists', false,
                    'record_count', 0,
                    'latest_date', NULL,
                    'oldest_date', NULL,
                    'age_days', NULL,
                    'source', NULL,
                    'data_origin', NULL,
                    'status', 'INSUFFICIENT_DATA',
                    'eligible_for_analyst', false,
                    'exclusion_reason', 'No valid price records found up to requested as-of date',
                    'details', '{}'::jsonb
                )
                ELSE jsonb_build_object(
                    'dataset', 'prices',
                    'exists', true,
                    'record_count', agg.cnt,
                    'latest_date', to_char(latest.observation_date, 'YYYY-MM-DD'),
                    'oldest_date', to_char(agg.min_dt, 'YYYY-MM-DD'),
                    'age_days', (p_as_of - latest.observation_date),
                    'source', COALESCE(latest.source, 'LOTUSMARKET'),
                    'data_origin', CASE
                        WHEN has_lin.exists_lin THEN 'LINEAGED_INGESTION'
                        WHEN COALESCE(latest.source, '') ~* '(DNSE|LOTUSMARKET|VNDIRECT|VIETCAP|VIETSTOCK|KBS)' THEN 'CANONICAL_MARKET_FEED'
                        WHEN upper(COALESCE(latest.source, '')) IN ('HOSE_CSV', 'MARKETDATACSV') THEN 'STATIC_OR_SEEDED'
                        ELSE 'SEEDED_OR_UNTRACED'
                    END,
                    'status', CASE WHEN (p_as_of - latest.observation_date) > 7 THEN 'STALE' ELSE 'AVAILABLE' END,
                    'eligible_for_analyst', (
                        (p_as_of - latest.observation_date) <= 7
                        AND (
                            has_lin.exists_lin
                            OR COALESCE(latest.source, '') ~* '(DNSE|LOTUSMARKET|VNDIRECT|VIETCAP|VIETSTOCK|KBS)'
                        )
                    ),
                    'exclusion_reason', CASE
                        WHEN (p_as_of - latest.observation_date) > 7 THEN 'Price is STALE (age: ' || (p_as_of - latest.observation_date) || ' days)'
                        WHEN NOT (has_lin.exists_lin OR COALESCE(latest.source, '') ~* '(DNSE|LOTUSMARKET|VNDIRECT|VIETCAP|VIETSTOCK|KBS)')
                             THEN 'Price origin is untraced or static'
                        ELSE NULL
                    END,
                    'details', jsonb_build_object('latest_close', latest.raw_close, 'volume', latest.volume)
                )
            END AS p_json
        FROM (
            SELECT COUNT(*)::int AS cnt, MIN(p.observation_date) AS min_dt
            FROM public.prices p
            WHERE p.asset_id = ta.id AND p.status = 'VALID' AND p.observation_date <= p_as_of
        ) agg
        LEFT JOIN LATERAL (
            SELECT p.id, p.observation_date, p.raw_close, p.volume, p.source
            FROM public.prices p
            WHERE p.asset_id = ta.id AND p.status = 'VALID' AND p.observation_date <= p_as_of
            ORDER BY p.observation_date DESC
            LIMIT 1
        ) latest ON true
        LEFT JOIN LATERAL (
            SELECT EXISTS (
                SELECT 1 FROM public.data_lineages dl
                WHERE dl.record_table = 'prices' AND dl.record_id = latest.id::text
            ) AS exists_lin
        ) has_lin ON true
    ) p_info
    CROSS JOIN LATERAL (
        SELECT
            (CASE WHEN ta.is_index OR upper(ta.asset_type) = 'ETF' THEN false ELSE (fagg.cnt > 0) END) AS has_fund,
            CASE
                WHEN ta.is_index OR upper(ta.asset_type) = 'ETF' THEN 'SKIPPED_UNSUPPORTED'
                WHEN fagg.cnt = 0 THEN 'INSUFFICIENT_DATA'
                WHEN (p_as_of - f_latest.fiscal_period_end) > 185 THEN 'STALE'
                ELSE 'AVAILABLE'
            END AS f_status,
            CASE
                WHEN ta.is_index OR upper(ta.asset_type) = 'ETF' THEN false
                WHEN fagg.cnt > 0 AND (p_as_of - f_latest.fiscal_period_end) <= 185 THEN true
                ELSE false
            END AS f_eligible,
            CASE
                WHEN ta.is_index OR upper(ta.asset_type) = 'ETF' THEN jsonb_build_object(
                    'dataset', 'fundamentals',
                    'exists', false,
                    'record_count', 0,
                    'latest_date', NULL,
                    'oldest_date', NULL,
                    'age_days', NULL,
                    'source', NULL,
                    'data_origin', NULL,
                    'status', 'SKIPPED_UNSUPPORTED',
                    'eligible_for_analyst', false,
                    'exclusion_reason', 'Indices and ETFs do not have standalone corporate financial statements.',
                    'details', '{}'::jsonb
                )
                WHEN fagg.cnt = 0 THEN jsonb_build_object(
                    'dataset', 'fundamentals',
                    'exists', false,
                    'record_count', 0,
                    'latest_date', NULL,
                    'oldest_date', NULL,
                    'age_days', NULL,
                    'source', NULL,
                    'data_origin', NULL,
                    'status', 'INSUFFICIENT_DATA',
                    'eligible_for_analyst', false,
                    'exclusion_reason', 'No financial statements ingested for this equity.',
                    'details', '{}'::jsonb
                )
                ELSE jsonb_build_object(
                    'dataset', 'fundamentals',
                    'exists', true,
                    'record_count', fagg.cnt,
                    'latest_date', to_char(f_latest.fiscal_period_end, 'YYYY-MM-DD'),
                    'oldest_date', to_char(fagg.min_dt, 'YYYY-MM-DD'),
                    'age_days', (p_as_of - f_latest.fiscal_period_end),
                    'source', COALESCE(f_latest.source_name, 'VNDIRECT_FINFO'),
                    'data_origin', 'CANONICAL_FINANCIAL_STATEMENTS',
                    'status', CASE WHEN (p_as_of - f_latest.fiscal_period_end) > 185 THEN 'STALE' ELSE 'AVAILABLE' END,
                    'eligible_for_analyst', ((p_as_of - f_latest.fiscal_period_end) <= 185),
                    'exclusion_reason', CASE WHEN (p_as_of - f_latest.fiscal_period_end) > 185
                        THEN 'Latest financial statement is stale (' || (p_as_of - f_latest.fiscal_period_end) || ' days old)'
                        ELSE NULL END,
                    'details', jsonb_build_object(
                        'statement_breakdown', COALESCE(f_types.by_type, '{}'::jsonb),
                        'latest_period', f_latest.fiscal_year::text || '_' || COALESCE(f_latest.fiscal_quarter::text, 'ANNUAL')
                    )
                )
            END AS f_json
        FROM (
            SELECT COUNT(*)::int AS cnt, MIN(fs.fiscal_period_end) AS min_dt
            FROM public.financial_statements fs
            WHERE fs.asset_id = ta.id AND fs.status = 'VALID' AND fs.fiscal_period_end <= p_as_of
        ) fagg
        LEFT JOIN LATERAL (
            SELECT fs.fiscal_period_end, fs.source_name, fs.fiscal_year, fs.fiscal_quarter
            FROM public.financial_statements fs
            WHERE fs.asset_id = ta.id AND fs.status = 'VALID' AND fs.fiscal_period_end <= p_as_of
            ORDER BY fs.fiscal_period_end DESC
            LIMIT 1
        ) f_latest ON true
        LEFT JOIN LATERAL (
            SELECT jsonb_object_agg(statement_type, type_cnt) AS by_type
            FROM (
                SELECT fs.statement_type, COUNT(*)::int AS type_cnt
                FROM public.financial_statements fs
                WHERE fs.asset_id = ta.id
                GROUP BY fs.statement_type
            ) t
        ) f_types ON true
    ) f_info
    CROSS JOIN LATERAL (
        SELECT
            CASE
                WHEN ta.is_index OR upper(ta.asset_type) = 'ETF' THEN jsonb_build_object(
                    'dataset', 'valuation', 'exists', false, 'record_count', 0,
                    'latest_date', NULL, 'oldest_date', NULL, 'age_days', NULL,
                    'source', NULL, 'data_origin', NULL, 'status', 'SKIPPED_UNSUPPORTED',
                    'eligible_for_analyst', false,
                    'exclusion_reason', 'Valuation multiples are not computed directly on benchmark indexes and ETFs.',
                    'details', '{}'::jsonb
                )
                WHEN p_info.p_status = 'AVAILABLE' AND f_info.f_status = 'AVAILABLE' THEN jsonb_build_object(
                    'dataset', 'valuation', 'exists', true, 'record_count', 1,
                    'latest_date', p_info.p_json->>'latest_date', 'oldest_date', NULL, 'age_days', NULL,
                    'source', 'InvestIntel.ValuationEngine', 'data_origin', 'CANONICAL_COMPUTATION',
                    'status', 'AVAILABLE', 'eligible_for_analyst', true, 'exclusion_reason', NULL,
                    'details', jsonb_build_object('ready_for_pe_pb', true)
                )
                WHEN p_info.has_price THEN jsonb_build_object(
                    'dataset', 'valuation', 'exists', false, 'record_count', 0,
                    'latest_date', NULL, 'oldest_date', NULL, 'age_days', NULL,
                    'source', NULL, 'data_origin', NULL, 'status', 'INSUFFICIENT_DATA',
                    'eligible_for_analyst', false,
                    'exclusion_reason', 'Price is available, but financial statements are missing or stale to calculate valuation ratios.',
                    'details', '{}'::jsonb
                )
                ELSE jsonb_build_object(
                    'dataset', 'valuation', 'exists', false, 'record_count', 0,
                    'latest_date', NULL, 'oldest_date', NULL, 'age_days', NULL,
                    'source', NULL, 'data_origin', NULL, 'status', 'INSUFFICIENT_DATA',
                    'eligible_for_analyst', false,
                    'exclusion_reason', 'Neither price nor fundamental inputs are available.',
                    'details', '{}'::jsonb
                )
            END AS v_json
    ) v_info
    CROSS JOIN LATERAL (
        SELECT
            (ev.cnt + ca.cnt)::int AS total_ev,
            CASE
                WHEN (ev.cnt + ca.cnt) > 0 THEN jsonb_build_object(
                    'dataset', 'events', 'exists', true, 'record_count', (ev.cnt + ca.cnt)::int,
                    'latest_date', ev.latest_dt, 'oldest_date', NULL, 'age_days', NULL,
                    'source', 'VNDIRECT_EVENTS', 'data_origin', 'CORPORATE_EVENTS_DISCLOSURE',
                    'status', 'AVAILABLE', 'eligible_for_analyst', true, 'exclusion_reason', NULL,
                    'details', jsonb_build_object('event_records', ev.cnt, 'corporate_actions', ca.cnt)
                )
                ELSE jsonb_build_object(
                    'dataset', 'events', 'exists', false, 'record_count', 0,
                    'latest_date', NULL, 'oldest_date', NULL, 'age_days', NULL,
                    'source', NULL, 'data_origin', NULL, 'status', 'INSUFFICIENT_DATA',
                    'eligible_for_analyst', false,
                    'exclusion_reason', 'No public corporate disclosures or events recorded.',
                    'details', '{}'::jsonb
                )
            END AS e_json
        FROM (
            SELECT
                COUNT(*)::int AS cnt,
                to_char(MAX(re.as_of_date), 'YYYY-MM-DD') AS latest_dt
            FROM recent_events re
            WHERE upper(coalesce(re.title, '')) LIKE '%' || ta.symbol || '%'
               OR upper(coalesce(re.impacts_txt, '')) LIKE '%' || ta.symbol || '%'
        ) ev
        CROSS JOIN (
            SELECT COUNT(*)::int AS cnt
            FROM public.corporate_actions c
            WHERE upper(c.symbol) = ta.symbol AND c.action_date <= p_as_of
        ) ca
    ) ev_info
    ORDER BY ta.symbol ASC;
$$;

-- 6. Public Supabase RPC Endpoints

CREATE OR REPLACE FUNCTION public.rpc_get_instrument_coverage(
    p_symbol text,
    p_as_of date DEFAULT CURRENT_DATE
)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, extensions, pg_temp
AS $$
    SELECT jsonb_build_object(
        'symbol', r.symbol,
        'canonical_symbol', r.symbol,
        'name', r.name,
        'exchange', r.exchange,
        'asset_type', r.asset_type,
        'as_of_date', to_char(p_as_of, 'YYYY-MM-DD'),
        'overall_status', r.overall_status,
        'analyst_ready', r.analyst_ready,
        'eligible_evidence_count', r.eligible_evidence_count,
        'missing_datasets', r.missing_datasets,
        'datasets', r.datasets
    )
    FROM public._fn_instrument_coverage_rows(p_as_of, p_symbol) r
    LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION public.rpc_get_universe_coverage_audit(
    p_as_of date DEFAULT CURRENT_DATE
)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, extensions, pg_temp
AS $$
    WITH rows AS (
        SELECT * FROM public._fn_instrument_coverage_rows(p_as_of, NULL)
    ),
    agg AS (
        SELECT
            COUNT(*)::int AS total,
            COUNT(*) FILTER (WHERE overall_status = 'AVAILABLE')::int AS fully_available,
            COUNT(*) FILTER (WHERE overall_status = 'PARTIAL')::int AS partially_available,
            COUNT(*) FILTER (WHERE overall_status NOT IN ('AVAILABLE', 'PARTIAL'))::int AS insufficient,
            COUNT(*) FILTER (WHERE price_eligible)::int AS prices_available,
            COUNT(*) FILTER (WHERE NOT price_eligible AND price_status = 'STALE')::int AS prices_stale,
            COUNT(*) FILTER (WHERE NOT price_eligible AND price_status <> 'STALE')::int AS prices_missing,
            COUNT(*) FILTER (WHERE fund_eligible)::int AS fundamentals_available,
            COUNT(*) FILTER (WHERE NOT fund_eligible AND NOT is_index AND upper(asset_type) <> 'ETF')::int AS fundamentals_missing,
            COALESCE((SELECT jsonb_agg(s) FROM (SELECT symbol AS s FROM rows WHERE overall_status = 'AVAILABLE' ORDER BY symbol LIMIT 15) q1), '[]'::jsonb) AS full_stack_symbols,
            COALESCE((SELECT jsonb_agg(s) FROM (SELECT symbol AS s FROM rows WHERE overall_status = 'PARTIAL' AND has_price_row ORDER BY symbol LIMIT 15) q2), '[]'::jsonb) AS price_only_symbols,
            COALESCE((SELECT jsonb_agg(s) FROM (SELECT symbol AS s FROM rows WHERE overall_status NOT IN ('AVAILABLE', 'PARTIAL') ORDER BY symbol LIMIT 15) q3), '[]'::jsonb) AS no_data_symbols
        FROM rows
    )
    SELECT jsonb_build_object(
        'status', CASE WHEN fully_available > 0 THEN 'HEALTHY' ELSE 'PARTIAL' END,
        'as_of_date', to_char(p_as_of, 'YYYY-MM-DD'),
        'summary', jsonb_build_object(
            'total_canonical_instruments', total,
            'fully_available_for_deep_analysis', fully_available,
            'partially_available_for_analyst', partially_available,
            'insufficient_data_instruments', insufficient,
            'analyst_callable_universe', fully_available + partially_available
        ),
        'dataset_breakdown', jsonb_build_object(
            'prices', jsonb_build_object(
                'available_count', prices_available,
                'stale_count', prices_stale,
                'missing_count', prices_missing,
                'coverage_rate_pct', CASE WHEN total > 0 THEN round((prices_available::numeric / total::numeric) * 100.0, 1)::double precision ELSE 0 END
            ),
            'fundamentals_equities', jsonb_build_object(
                'available_count', fundamentals_available,
                'missing_or_pending_count', fundamentals_missing
            )
        ),
        'categorized_instruments', jsonb_build_object(
            'full_stack_symbols', full_stack_symbols,
            'price_only_symbols_sample', price_only_symbols,
            'no_data_symbols_sample', no_data_symbols
        ),
        'systemic_diagnostics', jsonb_build_object(
            'root_cause_for_partial_universe',
            'LotusMarket and Vietcap have ingested price history across the VN100 universe via canonical feeds. Equities with full quarterly & annual filings report AVAILABLE across prices, fundamentals, and valuation.'
        )
    )
    FROM agg;
$$;

CREATE OR REPLACE FUNCTION public.rpc_get_screener_rows(
    p_universe text DEFAULT 'ALL',
    p_sector text DEFAULT NULL,
    p_limit integer DEFAULT 200
)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, extensions, pg_temp
AS $$
    SELECT COALESCE(jsonb_agg(to_jsonb(t)), '[]'::jsonb)
    FROM (
        SELECT *
        FROM public.mv_daily_screener_metrics m
        WHERE (
            upper(coalesce(p_universe, 'ALL')) = 'ALL'
            OR (upper(p_universe) = 'VN30' AND m.is_vn30)
            OR (upper(p_universe) = 'VN100' AND m.is_vn100)
        )
          AND (p_sector IS NULL OR trim(p_sector) = '' OR m.sector ILIKE '%' || trim(p_sector) || '%')
        ORDER BY m.symbol ASC
        LIMIT GREATEST(1, LEAST(coalesce(p_limit, 200), 500))
    ) t;
$$;

CREATE OR REPLACE FUNCTION public.rpc_get_watchlist_snapshot(
    p_as_of date DEFAULT CURRENT_DATE,
    p_limit integer DEFAULT 50,
    p_offset integer DEFAULT 0
)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, extensions, pg_temp
AS $$
    WITH items AS (
        SELECT
            wi.id,
            wi.asset_id,
            upper(a.symbol) AS symbol,
            a.name,
            a.sector,
            wi.thesis,
            COALESCE(wi.horizon, 'LONG_TERM') AS horizon,
            wi.invalidation,
            wi.last_reviewed_at,
            wi.last_changed_at
        FROM public.watchlist_items wi
        JOIN public.assets a ON a.id = wi.asset_id
        ORDER BY wi.last_changed_at DESC NULLS LAST, a.symbol ASC
        OFFSET GREATEST(0, coalesce(p_offset, 0))
        LIMIT GREATEST(1, LEAST(coalesce(p_limit, 50), 100))
    )
    SELECT COALESCE(jsonb_agg(
        jsonb_build_object(
            'id', it.id,
            'asset_id', it.asset_id,
            'symbol', it.symbol,
            'name', it.name,
            'sector', it.sector,
            'thesis', it.thesis,
            'horizon', it.horizon,
            'invalidation', it.invalidation,
            'last_reviewed_at', it.last_reviewed_at,
            'last_changed_at', it.last_changed_at,
            'latest_price', CASE WHEN lp.id IS NOT NULL THEN jsonb_build_object(
                'value', COALESCE(lp.adjusted_close, lp.raw_close),
                'raw_close', lp.raw_close,
                'adjusted_close', lp.adjusted_close,
                'as_of_date', to_char(lp.observation_date, 'YYYY-MM-DD'),
                'source', lp.source,
                'status', CASE WHEN (p_as_of - lp.observation_date) > 7 THEN 'STALE' ELSE 'AVAILABLE' END
            ) ELSE NULL END,
            'metrics', CASE WHEN mv.symbol IS NOT NULL THEN jsonb_build_object(
                'pe', mv.pe,
                'pb', mv.pb,
                'roe', mv.roe,
                'gross_margin', mv.gross_margin,
                'net_margin', mv.net_margin,
                'de_ratio', mv.de_ratio
            ) ELSE NULL END,
            'recent_snapshots', COALESCE(snaps.arr, '[]'::jsonb)
        )
    ), '[]'::jsonb)
    FROM items it
    LEFT JOIN LATERAL (
        SELECT p.id, p.observation_date, p.raw_close, p.adjusted_close, p.source
        FROM public.prices p
        WHERE p.asset_id = it.asset_id AND p.status = 'VALID' AND p.observation_date <= p_as_of
        ORDER BY p.observation_date DESC
        LIMIT 1
    ) lp ON true
    LEFT JOIN public.mv_daily_screener_metrics mv ON mv.symbol = it.symbol
    LEFT JOIN LATERAL (
        SELECT jsonb_agg(ws.snapshot_data ORDER BY ws.captured_at DESC, ws.id DESC) AS arr
        FROM (
            SELECT ws_inner.snapshot_data, ws_inner.captured_at, ws_inner.id
            FROM public.watchlist_snapshots ws_inner
            WHERE ws_inner.watchlist_id = it.id
            ORDER BY ws_inner.captured_at DESC, ws_inner.id DESC
            LIMIT 2
        ) ws
    ) snaps ON true;
$$;

CREATE OR REPLACE FUNCTION public.rpc_get_portfolio_snapshot(
    p_portfolio_id text DEFAULT 'personal',
    p_as_of date DEFAULT CURRENT_DATE
)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, extensions, pg_temp
AS $$
    SELECT jsonb_build_object(
        'account', (
            SELECT to_jsonb(pp)
            FROM public.personal_portfolios pp
            WHERE pp.id = coalesce(p_portfolio_id, 'personal')
            LIMIT 1
        ),
        'holdings', COALESCE((
            SELECT jsonb_agg(jsonb_build_object(
                'id', ph.id,
                'asset_id', a.id,
                'symbol', upper(a.symbol),
                'name', a.name,
                'sector', a.sector,
                'asset_type', a.asset_type,
                'quantity', ph.quantity::double precision,
                'average_cost', ph.average_cost::double precision,
                'acquisition_date', to_char(ph.acquisition_date, 'YYYY-MM-DD'),
                'role', ph.role,
                'horizon', ph.horizon,
                'notes', ph.notes,
                'current_price', COALESCE(lp.adjusted_close, lp.raw_close),
                'price_as_of', to_char(lp.observation_date, 'YYYY-MM-DD'),
                'price_source', lp.source
            ) ORDER BY a.symbol ASC)
            FROM public.portfolio_holdings ph
            JOIN public.assets a ON a.id = ph.asset_id
            LEFT JOIN LATERAL (
                SELECT p.observation_date, p.raw_close, p.adjusted_close, p.source
                FROM public.prices p
                WHERE p.asset_id = a.id AND p.status = 'VALID' AND p.observation_date <= p_as_of
                ORDER BY p.observation_date DESC
                LIMIT 1
            ) lp ON true
            WHERE ph.portfolio_id = coalesce(p_portfolio_id, 'personal')
        ), '[]'::jsonb),
        'targets', COALESCE((
            SELECT jsonb_agg(jsonb_build_object(
                'asset_id', pt.asset_id,
                'target_weight', pt.target_weight::double precision
            ))
            FROM public.portfolio_targets pt
            WHERE pt.portfolio_id = coalesce(p_portfolio_id, 'personal')
        ), '[]'::jsonb),
        'dca_plan', (
            SELECT to_jsonb(dp)
            FROM public.personal_dca_plans dp
            WHERE dp.portfolio_id = coalesce(p_portfolio_id, 'personal')
            ORDER BY dp.id ASC
            LIMIT 1
        )
    );
$$;

CREATE OR REPLACE FUNCTION public.rpc_get_system_observability()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, extensions, pg_temp
AS $$
    WITH job_agg AS (
        SELECT
            COUNT(*)::int AS total,
            COUNT(*) FILTER (WHERE status IN ('SUCCESS', 'IDEMPOTENT_UNCHANGED'))::int AS success,
            COUNT(*) FILTER (WHERE status = 'FAILED')::int AS failed,
            COUNT(*) FILTER (WHERE status = 'RUNNING')::int AS running,
            (SELECT status FROM public.analyst_automation_jobs ORDER BY id DESC LIMIT 1) AS latest_status
        FROM public.analyst_automation_jobs
    ),
    run_agg AS (
        SELECT
            COUNT(*)::int AS total_runs,
            COUNT(*) FILTER (WHERE status = 'SUCCESS')::int AS successful_runs,
            COUNT(*) FILTER (WHERE status IN ('FAILURE', 'FAILED'))::int AS failed_runs
        FROM public.data_runs
    ),
    sym_counts AS (
        SELECT upper(a.symbol) AS symbol, COUNT(p.id)::int AS cnt
        FROM public.prices p
        JOIN public.assets a ON a.id = p.asset_id
        GROUP BY upper(a.symbol)
    ),
    dups AS (
        SELECT COUNT(*)::int AS dup_cnt
        FROM (
            SELECT asset_id, observation_date
            FROM public.prices
            GROUP BY asset_id, observation_date
            HAVING COUNT(*) > 1
        ) d
    )
    SELECT jsonb_build_object(
        'background_jobs', jsonb_build_object(
            'total', j.total,
            'success', j.success,
            'failed', j.failed,
            'running', j.running,
            'latest_status', j.latest_status
        ),
        'ingestion', jsonb_build_object(
            'total_runs', r.total_runs,
            'successful_runs', r.successful_runs,
            'failed_runs', r.failed_runs
        ),
        'data_freshness', jsonb_build_object(
            'latest_price_date', (SELECT to_char(MAX(observation_date), 'YYYY-MM-DD') FROM public.prices),
            'latest_macro_date', (SELECT to_char(MAX(observation_date), 'YYYY-MM-DD') FROM public.macro_observations),
            'latest_statement_date', (SELECT to_char(MAX(fiscal_period_end), 'YYYY-MM-DD') FROM public.financial_statements),
            'total_price_records', (SELECT COUNT(*)::int FROM public.prices),
            'total_statements', (SELECT COUNT(*)::int FROM public.financial_statements),
            'total_lineages', (SELECT COUNT(*)::int FROM public.data_lineages),
            'lotusmarket_price_records', (SELECT COUNT(*)::int FROM public.prices WHERE source ILIKE '%LOTUSMARKET%'),
            'assets_with_prices_count', (SELECT COUNT(*)::int FROM sym_counts),
            'duplicate_prices_count', (SELECT dup_cnt FROM dups),
            'price_counts_by_symbol', COALESCE((SELECT jsonb_object_agg(symbol, cnt) FROM sym_counts), '{}'::jsonb)
        )
    )
    FROM job_agg j, run_agg r;
$$;

CREATE OR REPLACE FUNCTION public.rpc_get_universe_overview()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, extensions, pg_temp
AS $$
    SELECT jsonb_build_object(
        'total_active', (SELECT COUNT(*)::int FROM public.assets WHERE status = 'ACTIVE'),
        'by_exchange', COALESCE((
            SELECT jsonb_object_agg(exch, cnt)
            FROM (
                SELECT COALESCE(exchange, 'HOSE') AS exch, COUNT(*)::int AS cnt
                FROM public.assets
                WHERE status = 'ACTIVE'
                GROUP BY COALESCE(exchange, 'HOSE')
            ) e
        ), '{}'::jsonb),
        'by_type', COALESCE((
            SELECT jsonb_object_agg(atype, cnt)
            FROM (
                SELECT COALESCE(asset_type, 'STOCK') AS atype, COUNT(*)::int AS cnt
                FROM public.assets
                WHERE status = 'ACTIVE'
                GROUP BY COALESCE(asset_type, 'STOCK')
            ) t
        ), '{}'::jsonb),
        'vn100_active_members', (SELECT COUNT(*)::int FROM public.index_memberships WHERE index_symbol = 'VN100' AND is_active),
        'vn30_active_members', (SELECT COUNT(*)::int FROM public.index_memberships WHERE index_symbol = 'VN30' AND is_active),
        'active_symbols', COALESCE((
            SELECT jsonb_agg(upper(symbol) ORDER BY symbol)
            FROM public.assets
            WHERE status = 'ACTIVE'
        ), '[]'::jsonb),
        'sample_constituents', COALESCE((
            SELECT jsonb_agg(jsonb_build_object(
                'symbol', symbol,
                'name', name,
                'exchange', COALESCE(exchange, 'HOSE'),
                'asset_type', COALESCE(asset_type, 'STOCK'),
                'isin', isin,
                'sector', sector,
                'is_active', true,
                'is_index', (upper(COALESCE(asset_type, 'STOCK')) = 'INDEX'),
                'aliases', '[]'::jsonb,
                'source', 'CANONICAL_DATABASE',
                'asset_id', id
            ) ORDER BY symbol)
            FROM (
                SELECT id, symbol, name, exchange, asset_type, isin, sector
                FROM public.assets
                WHERE status = 'ACTIVE'
                ORDER BY symbol ASC
                LIMIT 5
            ) s
        ), '[]'::jsonb)
    );
$$;

DROP FUNCTION IF EXISTS public.rpc_match_document_chunks(text, text, date, integer, boolean);

CREATE OR REPLACE FUNCTION public.rpc_match_document_chunks(
    p_query text,
    p_ticker text DEFAULT NULL,
    p_as_of date DEFAULT CURRENT_DATE,
    p_limit integer DEFAULT 5,
    p_exclude_synthetic boolean DEFAULT true,
    p_query_embedding text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, extensions, pg_temp
AS $$
    WITH q AS (
        SELECT
            plainto_tsquery('simple', coalesce(p_query, '')) AS tsq,
            coalesce(trim(p_query), '') AS raw_q,
            CASE
                WHEN p_query_embedding IS NOT NULL AND length(trim(p_query_embedding)) > 4
                THEN (trim(p_query_embedding))::extensions.vector(768)
                ELSE NULL::extensions.vector(768)
            END AS qvec
    ),
    scored AS (
        SELECT
            dc.id,
            dc.document_id,
            dc.chunk_id,
            d.ticker,
            d.company,
            d.source,
            d.publication_date,
            d.period,
            d.document_type,
            d.language,
            d.title,
            dc.section,
            dc.page_reference,
            dc.text,
            COALESCE(ts_rank_cd(dc.search_tsv, q.tsq), 0.0)::double precision AS bm25_score,
            COALESCE(extensions.similarity(dc.text, q.raw_q), 0.0)::double precision AS trgm_score,
            CASE
                WHEN q.qvec IS NOT NULL AND dc.embedding_vec IS NOT NULL
                THEN GREATEST(0.0, 1.0 - (dc.embedding_vec <=> q.qvec))::double precision
                ELSE 0.0::double precision
            END AS dense_score,
            exp(-GREATEST(0, COALESCE(p_as_of, CURRENT_DATE) - COALESCE(d.publication_date, CURRENT_DATE))::double precision / 365.0) AS recency_weight
        FROM public.document_chunks dc
        JOIN public.documents d ON d.document_id = dc.document_id
        CROSS JOIN q
        WHERE d.status = 'READY'
          AND (NOT coalesce(p_exclude_synthetic, true) OR coalesce(d.is_synthetic, false) = false)
          AND (p_as_of IS NULL OR d.publication_date <= p_as_of)
          AND (
              p_ticker IS NULL
              OR trim(p_ticker) = ''
              OR upper(d.ticker) = ANY(string_to_array(upper(p_ticker), ','))
          )
          AND (
              (dc.search_tsv @@ q.tsq)
              OR (length(q.raw_q) >= 3 AND extensions.similarity(dc.text, q.raw_q) > 0.04)
              OR (q.qvec IS NOT NULL AND dc.embedding_vec IS NOT NULL AND (1.0 - (dc.embedding_vec <=> q.qvec)) > 0.12)
          )
    )
    SELECT COALESCE(jsonb_agg(row_json), '[]'::jsonb)
    FROM (
        SELECT jsonb_build_object(
            'document_id', document_id,
            'chunk_id', chunk_id,
            'ticker', ticker,
            'company', company,
            'source', source,
            'publication_date', to_char(publication_date, 'YYYY-MM-DD'),
            'period', period,
            'document_type', document_type,
            'language', language,
            'title', title,
            'section', section,
            'page_reference', page_reference,
            'text', text,
            'bm25_score', round(bm25_score::numeric, 6)::double precision,
            'dense_score', round(dense_score::numeric, 6)::double precision,
            'recency_weight', round(recency_weight::numeric, 4)::double precision,
            'score', round((((bm25_score * 0.45) + (trgm_score * 0.25) + (dense_score * 0.85)) * (0.55 + 0.45 * recency_weight))::numeric, 6)::double precision,
            'retrieval_mode', CASE
                WHEN dense_score > 0.0 THEN 'POSTGRES_HYBRID_PGVECTOR_TEMPORAL'
                ELSE 'POSTGRES_HYBRID_FTS_TRGM'
            END
        ) AS row_json
        FROM scored
        ORDER BY
            (((bm25_score * 0.45) + (trgm_score * 0.25) + (dense_score * 0.85)) * (0.55 + 0.45 * recency_weight)) DESC,
            publication_date DESC,
            id ASC
        LIMIT GREATEST(1, LEAST(coalesce(p_limit, 5), 25))
    ) ranked;
$$;

CREATE OR REPLACE FUNCTION public.rpc_get_pit_fundamentals_batch(
    p_symbols text[],
    p_as_of date DEFAULT CURRENT_DATE
)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, extensions, pg_temp
AS $$
    SELECT COALESCE(jsonb_object_agg(sym, sym_payload), '{}'::jsonb)
    FROM (
        SELECT
            upper(a.symbol) AS sym,
            jsonb_build_object(
                'symbol', upper(a.symbol),
                'name', a.name,
                'sector', COALESCE(NULLIF(trim(a.sector), ''), 'GENERAL'),
                'exchange', COALESCE(a.exchange, 'HOSE'),
                'shares_outstanding', (
                    SELECT fm.value::double precision
                    FROM public.fundamental_metrics fm
                    WHERE upper(fm.symbol) = upper(a.symbol)
                      AND fm.metric_id IN ('OUTSTANDING_SHARES', 'TOTAL_SHARES', 'LISTED_SHARES')
                      AND fm.value IS NOT NULL AND fm.value > 0
                    ORDER BY fm.fiscal_period_end DESC
                    LIMIT 1
                ),
                'latest_annual_income', (
                    SELECT to_jsonb(ni)
                    FROM public.normalized_income ni
                    JOIN public.financial_statements fs ON fs.id = ni.statement_id
                    WHERE upper(fs.symbol) = upper(a.symbol)
                      AND fs.status = 'VALID'
                      AND ni.period_type = 'ANNUAL'
                      AND (p_as_of IS NULL OR fs.publication_date <= p_as_of)
                    ORDER BY ni.fiscal_period_end DESC, fs.version DESC
                    LIMIT 1
                ),
                'recent_quarters_income', COALESCE((
                    SELECT jsonb_agg(to_jsonb(q) ORDER BY q.fiscal_period_end DESC)
                    FROM (
                        SELECT DISTINCT ON (ni.fiscal_period_end)
                            ni.fiscal_period_end, ni.fiscal_year, ni.fiscal_quarter,
                            ni.revenue, ni.gross_profit, ni.operating_income, ni.ebit,
                            ni.pre_tax_income, ni.income_tax, ni.net_income, ni.net_income_parent,
                            ni.eps_basic, ni.shares_basic, fs.publication_date
                        FROM public.normalized_income ni
                        JOIN public.financial_statements fs ON fs.id = ni.statement_id
                        WHERE upper(fs.symbol) = upper(a.symbol)
                          AND fs.status = 'VALID'
                          AND ni.period_type = 'QUARTERLY'
                          AND (p_as_of IS NULL OR fs.publication_date <= p_as_of)
                        ORDER BY ni.fiscal_period_end DESC, fs.version DESC, ni.id DESC
                        LIMIT 8
                    ) q
                ), '[]'::jsonb),
                'latest_balance_sheet', (
                    SELECT to_jsonb(nb)
                    FROM public.normalized_balance_sheets nb
                    JOIN public.financial_statements fs ON fs.id = nb.statement_id
                    WHERE upper(fs.symbol) = upper(a.symbol)
                      AND fs.status = 'VALID'
                      AND nb.period_type IN ('QUARTERLY', 'ANNUAL')
                      AND COALESCE(nb.equity_parent, nb.total_equity) IS NOT NULL
                      AND (p_as_of IS NULL OR fs.publication_date <= p_as_of)
                    ORDER BY nb.fiscal_period_end DESC, fs.version DESC, nb.id DESC
                    LIMIT 1
                )
            ) AS sym_payload
        FROM public.assets a
        WHERE upper(a.symbol) = ANY(
            SELECT DISTINCT upper(trim(x)) FROM unnest(coalesce(p_symbols, ARRAY[]::text[])) AS x
        )
    ) s;
$$;

CREATE OR REPLACE FUNCTION public.rpc_refresh_analytics_views()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, extensions, pg_temp
AS $$
DECLARE
    t0 timestamptz := clock_timestamp();
    row_cnt integer := 0;
BEGIN
    BEGIN
        REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_daily_screener_metrics;
    EXCEPTION WHEN OTHERS THEN
        REFRESH MATERIALIZED VIEW public.mv_daily_screener_metrics;
    END;
    SELECT COUNT(*)::int INTO row_cnt FROM public.mv_daily_screener_metrics;
    RETURN jsonb_build_object(
        'status', 'REFRESHED',
        'view', 'mv_daily_screener_metrics',
        'rows', row_cnt,
        'duration_ms', round((EXTRACT(EPOCH FROM (clock_timestamp() - t0)) * 1000)::numeric, 2)
    );
END;
$$;

-- 7. Stage 2 & 3 Additive Daily Foreign Flow Table + Cross-Sectional Factor Normalization RPC
CREATE TABLE IF NOT EXISTS public.market_flows_daily (
    id serial PRIMARY KEY,
    symbol varchar NOT NULL,
    observation_date date NOT NULL,
    foreign_buy_vol double precision,
    foreign_sell_vol double precision,
    foreign_buy_value double precision,
    foreign_sell_value double precision,
    foreign_net_value double precision,
    foreign_room double precision,
    source varchar DEFAULT 'VPS_MARKET_FEED',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz,
    CONSTRAINT uq_market_flow_symbol_date UNIQUE (symbol, observation_date)
);

CREATE INDEX IF NOT EXISTS idx_market_flows_daily_date_sym
    ON public.market_flows_daily (observation_date DESC, symbol);

CREATE OR REPLACE FUNCTION public.rpc_get_cross_sectional_features(
    p_as_of date DEFAULT CURRENT_DATE,
    p_symbol text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, extensions, pg_temp
AS $$
    WITH price_hist AS (
        SELECT
            upper(a.symbol) AS symbol,
            COALESCE(p.adjusted_close, p.raw_close)::double precision AS close_px,
            p.observation_date,
            ROW_NUMBER() OVER (PARTITION BY a.id ORDER BY p.observation_date DESC) AS rn
        FROM public.prices p
        JOIN public.assets a ON a.id = p.asset_id
        WHERE p.status = 'VALID'
          AND p.observation_date <= COALESCE(p_as_of, CURRENT_DATE)
          AND a.status = 'ACTIVE'
    ),
    mom AS (
        SELECT
            symbol,
            MAX(CASE WHEN rn = 1 THEN close_px END) AS px_0,
            MAX(CASE WHEN rn = 21 THEN close_px END) AS px_20,
            MAX(CASE WHEN rn = 61 THEN close_px END) AS px_60
        FROM price_hist
        WHERE rn IN (1, 21, 61)
        GROUP BY symbol
    ),
    universe AS (
        SELECT
            m.symbol,
            CASE
                WHEN upper(COALESCE(m.sector, '')) IN ('BANK', 'BANKING') THEN 'BANK'
                WHEN upper(COALESCE(m.sector, '')) IN ('OIL_GAS', 'ENERGY') THEN 'OIL_GAS'
                WHEN upper(COALESCE(m.sector, '')) IN ('MATERIALS') THEN 'MATERIALS'
                WHEN upper(COALESCE(m.sector, '')) IN ('CONSUMER', 'CONSUMER GOODS') THEN 'CONSUMER'
                WHEN upper(COALESCE(m.sector, '')) IN ('INDUSTRIAL', 'INDUSTRIALS') THEN 'INDUSTRIAL'
                WHEN upper(COALESCE(m.sector, '')) IN ('REAL ESTATE', 'REAL_ESTATE') THEN 'REAL_ESTATE'
                WHEN upper(COALESCE(m.sector, '')) IN ('UTILITY', 'UTILITIES') THEN 'UTILITY'
                WHEN upper(COALESCE(m.sector, '')) IN ('RETAIL') THEN 'RETAIL'
                WHEN upper(COALESCE(m.sector, '')) IN ('TECHNOLOGY') THEN 'TECHNOLOGY'
                WHEN upper(COALESCE(m.sector, '')) IN ('SECURITIES', 'FINANCIALS') THEN 'SECURITIES'
                WHEN upper(COALESCE(m.sector, '')) IN ('TRANSPORTATION') THEN 'TRANSPORTATION'
                ELSE COALESCE(NULLIF(upper(trim(m.sector)), ''), 'GENERAL')
            END AS norm_sector,
            CASE WHEN m.pe IS NOT NULL AND m.pe > 0 AND m.pe <= 150 THEN m.pe ELSE NULL END AS pe,
            CASE WHEN m.pb IS NOT NULL AND m.pb > 0 AND m.pb <= 25 THEN m.pb ELSE NULL END AS pb,
            CASE WHEN m.roe IS NOT NULL AND m.roe BETWEEN -60 AND 80 THEN m.roe ELSE NULL END AS roe,
            CASE WHEN m.gross_margin IS NOT NULL AND m.gross_margin BETWEEN -50 AND 95 THEN m.gross_margin ELSE NULL END AS gross_margin,
            CASE WHEN m.net_margin IS NOT NULL AND m.net_margin BETWEEN -60 AND 85 THEN m.net_margin ELSE NULL END AS net_margin,
            CASE WHEN m.de_ratio IS NOT NULL AND m.de_ratio BETWEEN 0 AND 15 THEN m.de_ratio ELSE NULL END AS de_ratio,
            CASE WHEN mom.px_0 IS NOT NULL AND mom.px_20 IS NOT NULL AND mom.px_20 > 0
                 THEN ((mom.px_0 - mom.px_20) / mom.px_20) * 100.0 ELSE NULL END AS mom_20d,
            CASE WHEN mom.px_0 IS NOT NULL AND mom.px_60 IS NOT NULL AND mom.px_60 > 0
                 THEN ((mom.px_0 - mom.px_60) / mom.px_60) * 100.0 ELSE NULL END AS mom_60d
        FROM public.mv_daily_screener_metrics m
        LEFT JOIN mom ON mom.symbol = m.symbol
    ),
    sector_stats AS (
        SELECT
            u.*,
            COUNT(*) OVER (PARTITION BY u.norm_sector) AS peer_count,
            AVG(u.pe) OVER (PARTITION BY u.norm_sector) AS mean_pe,
            NULLIF(STDDEV_SAMP(u.pe) OVER (PARTITION BY u.norm_sector), 0.0) AS std_pe,
            AVG(u.pb) OVER (PARTITION BY u.norm_sector) AS mean_pb,
            NULLIF(STDDEV_SAMP(u.pb) OVER (PARTITION BY u.norm_sector), 0.0) AS std_pb,
            AVG(u.roe) OVER (PARTITION BY u.norm_sector) AS mean_roe,
            NULLIF(STDDEV_SAMP(u.roe) OVER (PARTITION BY u.norm_sector), 0.0) AS std_roe,
            AVG(u.gross_margin) OVER (PARTITION BY u.norm_sector) AS mean_gm,
            NULLIF(STDDEV_SAMP(u.gross_margin) OVER (PARTITION BY u.norm_sector), 0.0) AS std_gm,
            AVG(u.net_margin) OVER (PARTITION BY u.norm_sector) AS mean_nm,
            NULLIF(STDDEV_SAMP(u.net_margin) OVER (PARTITION BY u.norm_sector), 0.0) AS std_nm,
            AVG(u.de_ratio) OVER (PARTITION BY u.norm_sector) AS mean_de,
            NULLIF(STDDEV_SAMP(u.de_ratio) OVER (PARTITION BY u.norm_sector), 0.0) AS std_de,
            AVG(u.mom_20d) OVER (PARTITION BY u.norm_sector) AS mean_mom20,
            NULLIF(STDDEV_SAMP(u.mom_20d) OVER (PARTITION BY u.norm_sector), 0.0) AS std_mom20,
            AVG(u.mom_60d) OVER (PARTITION BY u.norm_sector) AS mean_mom60,
            NULLIF(STDDEV_SAMP(u.mom_60d) OVER (PARTITION BY u.norm_sector), 0.0) AS std_mom60
        FROM universe u
    )
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'symbol', s.symbol,
        'sector', s.norm_sector,
        'peer_count', s.peer_count,
        'pe', round(s.pe::numeric, 2)::double precision,
        'pb', round(s.pb::numeric, 2)::double precision,
        'roe', round(s.roe::numeric, 2)::double precision,
        'gross_margin', round(s.gross_margin::numeric, 2)::double precision,
        'net_margin', round(s.net_margin::numeric, 2)::double precision,
        'de_ratio', round(s.de_ratio::numeric, 3)::double precision,
        'mom_20d', round(s.mom_20d::numeric, 2)::double precision,
        'mom_60d', round(s.mom_60d::numeric, 2)::double precision,
        'sector_mean_pe', round(s.mean_pe::numeric, 2)::double precision,
        'sector_mean_pb', round(s.mean_pb::numeric, 2)::double precision,
        'sector_mean_roe', round(s.mean_roe::numeric, 2)::double precision,
        'sector_mean_mom_20d', round(s.mean_mom20::numeric, 2)::double precision,
        'z_pe', CASE WHEN s.pe IS NOT NULL AND s.mean_pe IS NOT NULL AND s.std_pe IS NOT NULL
                     THEN round(GREATEST(-3.5, LEAST(3.5, (s.pe - s.mean_pe) / s.std_pe))::numeric, 3)::double precision ELSE NULL END,
        'z_pb', CASE WHEN s.pb IS NOT NULL AND s.mean_pb IS NOT NULL AND s.std_pb IS NOT NULL
                     THEN round(GREATEST(-3.5, LEAST(3.5, (s.pb - s.mean_pb) / s.std_pb))::numeric, 3)::double precision ELSE NULL END,
        'z_roe', CASE WHEN s.roe IS NOT NULL AND s.mean_roe IS NOT NULL AND s.std_roe IS NOT NULL
                      THEN round(GREATEST(-3.5, LEAST(3.5, (s.roe - s.mean_roe) / s.std_roe))::numeric, 3)::double precision ELSE NULL END,
        'z_gross_margin', CASE WHEN s.gross_margin IS NOT NULL AND s.mean_gm IS NOT NULL AND s.std_gm IS NOT NULL
                               THEN round(GREATEST(-3.5, LEAST(3.5, (s.gross_margin - s.mean_gm) / s.std_gm))::numeric, 3)::double precision ELSE NULL END,
        'z_net_margin', CASE WHEN s.net_margin IS NOT NULL AND s.mean_nm IS NOT NULL AND s.std_nm IS NOT NULL
                             THEN round(GREATEST(-3.5, LEAST(3.5, (s.net_margin - s.mean_nm) / s.std_nm))::numeric, 3)::double precision ELSE NULL END,
        'z_de_ratio', CASE WHEN s.de_ratio IS NOT NULL AND s.mean_de IS NOT NULL AND s.std_de IS NOT NULL
                           THEN round(GREATEST(-3.5, LEAST(3.5, (s.de_ratio - s.mean_de) / s.std_de))::numeric, 3)::double precision ELSE NULL END,
        'z_mom_20d', CASE WHEN s.mom_20d IS NOT NULL AND s.mean_mom20 IS NOT NULL AND s.std_mom20 IS NOT NULL
                          THEN round(GREATEST(-3.5, LEAST(3.5, (s.mom_20d - s.mean_mom20) / s.std_mom20))::numeric, 3)::double precision ELSE NULL END,
        'z_mom_60d', CASE WHEN s.mom_60d IS NOT NULL AND s.mean_mom60 IS NOT NULL AND s.std_mom60 IS NOT NULL
                          THEN round(GREATEST(-3.5, LEAST(3.5, (s.mom_60d - s.mean_mom60) / s.std_mom60))::numeric, 3)::double precision ELSE NULL END
    ) ORDER BY s.symbol), '[]'::jsonb)
    FROM sector_stats s
    WHERE p_symbol IS NULL OR trim(p_symbol) = '' OR upper(s.symbol) = upper(trim(p_symbol));
$$;

-- 8. Optional pg_cron schedule for nightly view refresh (never fails migration if unprivileged)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
        PERFORM cron.unschedule('investintel-refresh-screener-mv');
        PERFORM cron.schedule('investintel-refresh-screener-mv', '0 9 * * 1-5', 'SELECT public.rpc_refresh_analytics_views();');
    END IF;
EXCEPTION WHEN OTHERS THEN
    NULL;
END $$;

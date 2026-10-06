/*
STC PREPAID DATA MODEL NOTES
============================
Evidence used: table/view DDL plus the distinct-value extracts in sample_data.

Grain terminology:
  * "Intended grain" is inferred from the business columns, joins and indexes.
  * A Teradata PRIMARY INDEX controls row distribution; it is not a primary-key
    or uniqueness constraint. SET tables only reject exact duplicate rows, and
    MULTISET tables allow them. Validate the proposed grain on full row-level
    data before relying on it for counts or one-to-one joins.

Common keys and codes:
  * ROOT_SUBS_KEY: stable subscription/line key used across facts and RGS views.
  * ACCS_METH_KEY / ACCS_METH_VAL: access-method key/value, normally the served
    line or MSISDN-level access identifier.
  * ACCNT_KEY / CUST_KEY: account and customer warehouse keys; a customer may
    own multiple accounts and subscriptions.
  * RGS: revenue-generating subscriber; these views use 30-day RGS activity.
  * ATL / BTL: above-the-line / below-the-line package or revenue classification.
  * Observed LINE_TYPE values are PP, PS and TL, and SCREEN_TYPE values include
    SS, LS and NA. The shared sales/churn/snapshot tables are therefore not
    prepaid-only; prepaid reporting must apply the approved STC scope filters.
  * Text values contain mixed case, repeated/non-breaking spaces, Arabic/English
    labels and several unknown conventions (NA, UNK, UNKNOWN, SMBB-NA). Join on
    warehouse/source keys, not display names, and normalize labels only in a
    governed reporting layer.
*/

/*
Table: DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION
Purpose: Periodic subscriber-line revenue attribution and activity snapshot used
         for prepaid base, retention, churn and reconnect segmentation.
Intended grain: one ROOT_SUBS_KEY per REF_DATE and MNTHLY_WKLY_FLAG snapshot.
Additive measures: revenue columns are additive across subscribers for one
                   non-overlapping snapshot period; do not sum weekly and monthly
                   rows together.
*/
CREATE SET TABLE DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION ,FALLBACK ,
     NO BEFORE JOURNAL,
     NO AFTER JOURNAL,
     CHECKSUM = DEFAULT,
     DEFAULT MERGEBLOCKRATIO,
     MAP = TD_MAP3
     (
      REF_DATE DATE FORMAT 'yyyy-mm-dd', -- Snapshot/as-of date.
      MNTHLY_WKLY_FLAG VARCHAR(1) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Snapshot cadence (for example M or W).
      ACCS_METH_KEY DECIMAL(18,0), -- Warehouse key for the served access method/line.
      ACCNT_KEY INTEGER, -- Billing/customer account key.
      CUST_KEY INTEGER, -- Customer-party key.
      SCREEN_TYPE VARCHAR(2) CHARACTER SET UNICODE NOT CASESPECIFIC, -- STC reporting population code; confirm SS/LS definition with data owner.
      ROOT_SUBS_KEY DECIMAL(18,0), -- Stable subscription key; principal analytical entity.
      RATEPLAN VARCHAR(255) CHARACTER SET LATIN NOT CASESPECIFIC, -- Rate plan held at the snapshot date.
      LINE_START_DATE DATE FORMAT 'yyyy-mm-dd', -- Original/current subscription activation date used for tenure.
      SALES_COHORT_MONTH VARCHAR(5) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Months since sale, coded 00, 01, 02 ... or OLDER.
      TOTAL_REV FLOAT, -- Total attributed revenue for the snapshot period.
      ATL_REV FLOAT, -- Revenue attributed to above-the-line packages.
      BTL_REV FLOAT, -- Revenue attributed to below-the-line packages.
      RGS_30D_REV FLOAT, -- Revenue used in the rolling 30-day RGS qualification.
      RGS_30_FLAG VARCHAR(1) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Y when the line qualifies as 30-day RGS.
      ACTIVE_30_FLAG VARCHAR(1) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Activity indicator over the latest 30-day window.
      ACTIVE_60_FLAG VARCHAR(1) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Activity indicator over the latest 60-day window.
      ACTIVE_90_FLAG VARCHAR(1) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Activity indicator over the latest 90-day window.
      RGS_30_CU_FLAG VARCHAR(1) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Current-usage component/qualification of the 30-day RGS rule; confirm exact rule.
      OWNERSHIP_CHANGE_FLAG VARCHAR(1) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Ownership-transfer indicator for the line/period.
      PERIOD_END_ACT_FLAG VARCHAR(1) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Y when active at the relevant period end.
      BUNDLE_TYPE VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC, -- Revenue/package class such as ATL, BTL, PG Telcom or dormant prorated bundle.
      BUNDLE_NAME VARCHAR(250) CHARACTER SET LATIN NOT CASESPECIFIC, -- Dominant/attributed bundle name for the period.
      PAYG_TELECOM_REV FLOAT, -- Pay-as-you-go core telecom revenue.
      BUNDLE_FREQ_M BYTEINT, -- Number/frequency of bundle purchases in the monthly lookback; confirm window.
      BUNDLE_RCNCY_M BYTEINT, -- Bundle recency in months; confirm zero/one-based convention.
      CNT_LAST_4MS_CU INTEGER) -- Count of months with current usage in the last four months; 4 is treated as Core Base.
PRIMARY INDEX ( MNTHLY_WKLY_FLAG ,CUST_KEY ,ROOT_SUBS_KEY )
PARTITION BY RANGE_N(REF_DATE  BETWEEN DATE '2015-01-01' AND DATE '2035-12-31' EACH INTERVAL '1' DAY )
INDEX IDX_F_PP_BASE_REV_ATTRIBUTION_2_03 ( ACCS_METH_KEY );



/*
Table: DP_EDW_PPF.F_PP_PACKAGE_SUBSCRIPTIONS
Purpose: Transaction/event fact for package activations or subscriptions across
         EVD, IRB, MySTC, recharge, SCRM and SDP source flows.
Intended grain: one source package-subscription event, preferably identified by
                SYSTEM_RECORD_UID; otherwise by source + ROOT_SUBS_KEY/PCKG_ID +
                SUBSCRIPTION_START_DTTM. This is MULTISET, so duplicates are allowed.
Observed scope: SCREEN_TYPE contains LS and SS and RATEPLAN includes voice,
                QuickNet, prepaid and postpaid-like labels; do not infer prepaid
                scope from the table name alone.
*/
CREATE MULTISET TABLE DP_EDW_PPF.F_PP_PACKAGE_SUBSCRIPTIONS ,FALLBACK ,
     NO BEFORE JOURNAL,
     NO AFTER JOURNAL,
     CHECKSUM = DEFAULT,
     DEFAULT MERGEBLOCKRATIO,
     MAP = TD_MAP3
     (
      DATA_SOURCE VARCHAR(50) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Originating platform/feed (observed EVD, IRB, MYSTC, Recharge, SCRM, SDP).
      MSISDN VARCHAR(200) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Subscriber telephone/access number; sensitive identifier.
      ACCNT_KEY INTEGER,
      ACCS_METH_KEY DECIMAL(18,0),
      CUST_KEY INTEGER,
      SCREEN_TYPE VARCHAR(3) CHARACTER SET UNICODE NOT CASESPECIFIC, -- STC reporting population code (observed LS and SS).
      PACKAGEX VARCHAR(255) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Source/display package name; sample contains Yemen Weekly.
      PCKG_ID VARCHAR(50) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Canonical package key joining to D_PP_PACKAGE.
      SUBSCRIPTION_START_DT DATE FORMAT 'yyyy-mm-dd',
      SUBSCRIPTION_START_DTTM TIMESTAMP(0),
      SUBSCRIPTION_END_DT DATE FORMAT 'yyyy-mm-dd',
      SUBSCRIPTION_END_DTTM TIMESTAMP(0),
      SUBSCRIPTION_REVENUE DECIMAL(18,2), -- Revenue recognized/captured for the event in source currency (normally SAR; confirm).
      SUBSCRIPTION_CNT INTEGER, -- Event quantity/count; sum instead of counting rows when populated by source aggregation.
      SYSTEM_RECORD_UID VARCHAR(50) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Source event identifier and preferred deduplication key.
      SRC_SYS_INFO_1 VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Source-specific audit attribute; meaning varies by DATA_SOURCE.
      SRC_SYS_INFO_2 VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Second source-specific audit attribute.
      ROOT_SUBS_KEY DECIMAL(18,0), -- Stable subscription/line key.
      RATEPLAN VARCHAR(255) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Subscriber rate plan at subscription time.
      CHANNEL VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Activation/purchase channel (for example MySTC, CRM, USSD/SMS, voucher or gift).
      GIFTER VARCHAR(200) CHARACTER SET LATIN NOT CASESPECIFIC) -- Gifting party identifier when the package was gifted; sensitive.
PRIMARY INDEX ( CUST_KEY ,PCKG_ID ,ROOT_SUBS_KEY )
PARTITION BY RANGE_N(SUBSCRIPTION_START_DT  BETWEEN DATE '2015-01-01' AND DATE '2035-12-31' EACH INTERVAL '1' DAY )
INDEX IDX_F_PP_PACKAGE_SUBS_03 ( MSISDN );


/*
Table: DP_EDW_PPF.F_LINE_SALES
Purpose: Line-level service-order events used to identify acquisitions, migrations,
         reconnects and transfers, including the first revenue-generating date.
Intended grain: one service-order line per SERVICE_ORDER_NUM. ORDER_ID may group
                multiple service-order lines. The PRIMARY INDEX does not enforce
                SERVICE_ORDER_NUM uniqueness.
Observed codes: SALES_FLAG is Sales or Transfer; ORDER_TYP_NME includes New,
                Migrate, Modify, Transfer and Change of Technology. LINE_TYPE is
                PP/PS/TL, so apply an explicit prepaid filter approved by STC.
*/
CREATE SET TABLE DP_EDW_PPF.F_LINE_SALES ,FALLBACK ,
     NO BEFORE JOURNAL,
     NO AFTER JOURNAL,
     CHECKSUM = DEFAULT,
     DEFAULT MERGEBLOCKRATIO,
     MAP = TD_MAP3
     (
      ORDER_STRT_DT DATE FORMAT 'YY/MM/DD', -- Date the service order started.
      ORDER_END_DT DATE FORMAT 'YY/MM/DD', -- Date the service order completed/closed.
      SERVICE_ORDER_NUM VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC, -- Service-order line identifier and join key to F_LINE_SALES_ATTR.
      ORDER_ID DECIMAL(18,0), -- Parent/order identifier; may span multiple service-order lines.
      ACCS_METH_KEY DECIMAL(18,0),
      ACCNT_KEY INTEGER,
      CUST_KEY INTEGER,
      ORDER_TYP_NME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC, -- High-level order action.
      ORDER_SUBTYP_NME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Detailed action such as New, MNPPortIn, Reconnect or ownership/plan transfer.
      LINE_TYPE VARCHAR(2) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Line population code (observed PP, PS, TL).
      SCREEN_TYPE VARCHAR(2) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Reporting population code (observed LS, SS, NA).
      TECH_SUB_TYPE VARCHAR(255) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Access technology subtype (for example GSM/FTTH/FWA/COPPER when present).
      SERVICE_TYPE VARCHAR(255) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Service family such as VOICE, BROADBAND or FWA.
      PROD_KEY INTEGER, -- Product dimension key.
      RATE_PLAN_GRP_NME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Normalized/grouped rate-plan family.
      RATE_PLAN_NME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Specific rate-plan name on the order.
      ROOT_SUBS_KEY DECIMAL(18,0), -- Stable subscription/line key.
      SALES_FLAG VARCHAR(30) CHARACTER SET LATIN NOT CASESPECIFIC, -- Reporting classification; observed Sales or Transfer.
      FIRST_RG_DATE DATE FORMAT 'yyyy-mm-dd') -- First revenue-generating date; used to separate new sales from reconnects.
PRIMARY INDEX ( SERVICE_ORDER_NUM )
INDEX F_LINE_SALES_IDX_01 ( ORDER_END_DT )
INDEX F_LINE_SALES_IDX_02 ( ORDER_STRT_DT )
INDEX F_LINE_SALES_IDX_03 ( CUST_KEY )
INDEX F_LINE_SALES_IDX_04 ( LINE_TYPE )
INDEX F_LINE_SALES_IDX_05 ( SCREEN_TYPE )
INDEX F_LINE_SALES_IDX_06 ( PROD_KEY )
INDEX F_LINE_SALES_IDX_07 ( ORDER_ID )
INDEX F_LINE_SALES_IDX_08 ( ACCS_METH_KEY ,ACCNT_KEY )
INDEX F_LINE_SALES_IDX_09 ( ORDER_END_DT ,SALES_FLAG );


/*
Table: DP_EDW_PPF.F_LINE_SALES_ATTR
Purpose: Descriptive acquisition attributes for a service-order line: customer
         age, online package, port-in operator, SIM/offer, source and channel.
Intended grain: one enrichment row per SERVICE_ORDER_NUM, joined to F_LINE_SALES.
                Validate uniqueness before treating the join as one-to-one.
*/
CREATE SET TABLE DP_EDW_PPF.F_LINE_SALES_ATTR ,FALLBACK ,
     NO BEFORE JOURNAL,
     NO AFTER JOURNAL,
     CHECKSUM = DEFAULT,
     DEFAULT MERGEBLOCKRATIO,
     MAP = TD_MAP3
     (
      SERVICE_ORDER_NUM VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC, -- Join key to F_LINE_SALES.
      CUST_AGE INTEGER, -- Customer age at acquisition/order time.
      OLP_PCKG VARCHAR(255) CHARACTER SET LATIN NOT CASESPECIFIC, -- Online/ordered package label captured by the sales flow.
      MNP_FROM_OPR VARCHAR(255) CHARACTER SET LATIN NOT CASESPECIFIC, -- Donor operator for mobile-number port-in (for example Mobily, Zain, Virgin).
      SIM_TYPE VARCHAR(255) CHARACTER SET LATIN NOT CASESPECIFIC, -- Sold SIM/offer variant; values are commercial SAWA labels, not only physical/eSIM form factor.
      FIRST_USAGE_DATE DATE FORMAT 'YY/MM/DD', -- First observed usage date after sale.
      EVENT_SOURCE_TYPE_NAME VARCHAR(150) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Originating application/portal (for example MySTC, eDealer, kiosk or CRM).
      CHANNEL VARCHAR(150) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Rolled-up sales channel such as Digital, Retail or Distribution.
      SUB_CHANNEL VARCHAR(150) CHARACTER SET UNICODE NOT CASESPECIFIC, -- More detailed route-to-market/channel.
      FIRST_RECHARGE_DATE DATE FORMAT 'YY/MM/DD') -- First recharge date after sale.
PRIMARY INDEX ( SERVICE_ORDER_NUM );


/*
Table: DP_EDW_PPF.F_LINE_CHURN
Purpose: Service-order events representing disconnection, migration or transfer;
         used to classify explicit churn reasons and transfer events.
Intended grain: one service-order line/event per SERVICE_ORDER_NUM. The table can
                contain non-churn transfers (CHURN_FLAG = Transfer) and shared
                PP/PS/TL populations, so filter CHURN_FLAG and line scope explicitly.
*/
CREATE SET TABLE DP_EDW_PPF.F_LINE_CHURN ,FALLBACK ,
     NO BEFORE JOURNAL,
     NO AFTER JOURNAL,
     CHECKSUM = DEFAULT,
     DEFAULT MERGEBLOCKRATIO,
     MAP = TD_MAP3
     (
      ORDER_STRT_DT DATE FORMAT 'yyyy-mm-dd', -- Event/order start date.
      ORDER_END_DT DATE FORMAT 'yyyy-mm-dd', -- Effective completion date used as churn date in daily logic.
      SERVICE_ORDER_NUM VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC, -- Service-order line/event identifier.
      ORDER_ID DECIMAL(18,0), -- Parent/order identifier.
      ACCS_METH_KEY DECIMAL(18,0),
      ACCNT_KEY INTEGER,
      CUST_KEY INTEGER,
      ORDER_TYP_NME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC, -- High-level action; observed Disconnect, Migrate and Transfer.
      ORDER_SUBTYP_NME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Detailed reason/action (customer/system initiated, port-out, dunning, ownership, etc.).
      LINE_TYPE VARCHAR(2) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Line population code (observed PP, PS, TL).
      SCREEN_TYPE VARCHAR(2) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Reporting population code (observed LS, SS, NA).
      TECH_SUB_TYPE VARCHAR(255) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Access technology subtype.
      SERVICE_TYPE VARCHAR(255) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Service family such as BROADBAND or FWA in the supplied sample.
      PROD_KEY INTEGER, -- Product dimension key.
      RATE_PLAN_GRP_NME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Normalized/grouped rate-plan family at event time.
      RATE_PLAN_NME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Specific rate-plan name at event time.
      ROOT_SUBS_KEY DECIMAL(18,0), -- Stable subscription/line key used by RGS views.
      CHURN_FLAG VARCHAR(30) CHARACTER SET LATIN NOT CASESPECIFIC) -- Reporting classification; observed Churn or Transfer.
PRIMARY INDEX ( SERVICE_ORDER_NUM )
INDEX F_LINE_CHURN_IDX_01 ( ORDER_END_DT )
INDEX F_LINE_CHURN_IDX_02 ( ORDER_STRT_DT )
INDEX F_LINE_CHURN_IDX_03 ( CUST_KEY )
INDEX F_LINE_CHURN_IDX_04 ( LINE_TYPE )
INDEX F_LINE_CHURN_IDX_05 ( SCREEN_TYPE )
INDEX F_LINE_CHURN_IDX_06 ( PROD_KEY )
INDEX F_LINE_CHURN_IDX_07 ( ORDER_ID )
INDEX F_LINE_CHURN_IDX_08 ( ACCS_METH_KEY ,ACCNT_KEY )
INDEX F_LINE_CHURN_IDX_09 ( ORDER_END_DT ,CHURN_FLAG );

/*
Table: DP_EDW_PPF.F_MOBILITY_360
Purpose: Wide subscriber/account 360 snapshot combining lifecycle status, customer
         and device profile, recent activity/revenue/usage, recharge behavior,
         location, complaints, segmentation and network-experience features.
Intended grain: one access-method/account combination per REF_DATE snapshot,
                approximately REF_DATE + ACCS_METH_KEY + ACCNT_KEY. Validate this
                composite because the PRIMARY INDEX omits REF_DATE and is not unique.
Measure windows: LAST_1M/LAST_MONTH, LAST_3M and LAST_6M fields are rolling lookbacks
                 as of REF_DATE; they must not be summed across snapshot dates.
Privacy: MSISDN/access values, national ID, name, birth date and coordinates are
         sensitive personal/location data and should be masked in QA extracts.
Observed scope: product and screen values include mobile, QuickNet, Baity and other
                populations; use approved prepaid scope filters.
*/
CREATE SET TABLE DP_EDW_PPF.F_MOBILITY_360 ,FALLBACK ,
     NO BEFORE JOURNAL,
     NO AFTER JOURNAL,
     CHECKSUM = DEFAULT,
     DEFAULT MERGEBLOCKRATIO,
     MAP = TD_MAP3
     (
      -- Snapshot identity and subscription status.
      REF_DATE DATE FORMAT 'YY/MM/DD', -- Snapshot/as-of date.
      ACCS_METH_VAL VARCHAR(200) CHARACTER SET LATIN NOT CASESPECIFIC, -- Access-method value, commonly MSISDN/served number; sensitive.
      ACCS_METH_KEY DECIMAL(18,0), -- Warehouse key for the access method/line.
      ACCNT_NMBR VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC, -- Source account number; sensitive.
      ACCNT_KEY INTEGER, -- Warehouse account key.
      LINE_TYPE VARCHAR(2) CHARACTER SET UNICODE NOT CASESPECIFIC,
      SCREEN_TYPE VARCHAR(2) CHARACTER SET UNICODE NOT CASESPECIFIC,
      TECH_SUB_TYPE VARCHAR(3) CHARACTER SET UNICODE NOT CASESPECIFIC,
      SUBS_PROD_STS_TYP_NM VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Subscription-product status (Active, barred, suspended, etc.).
      ACCNT_STS_TYP_NME VARCHAR(100) CHARACTER SET LATIN NOT CASESPECIFIC, -- Account lifecycle/service status.
      ROOT_SUBS_KEY DECIMAL(18,0), -- Stable subscription/line key.
      LINE_ACTIVATION_DT DATE FORMAT 'YY/MM/DD', -- Line activation/start date.
      PROD_NME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Current product/rate-plan name.
      CRM_PROD_ID VARCHAR(50) CHARACTER SET UNICODE NOT CASESPECIFIC,
      -- Customer profile and segmentation.
      CUST_KEY INTEGER, -- Customer-party warehouse key.
      CUST_IDENT_NUM VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC, -- National/customer identity number; highly sensitive.
      CUST_BLCKLST_FLG VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC,
      CUST_BLCKLST_STS_NME VARCHAR(100) CHARACTER SET LATIN NOT CASESPECIFIC,
      FRST_NME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC,
      LST_NME VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC,
      FULL_NME VARCHAR(500) CHARACTER SET UNICODE NOT CASESPECIFIC,
      CUST_IDENT_SUB_TYP_CD VARCHAR(50) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Source identity subtype code (sample includes IREG-* codes).
      ID_TYPE VARCHAR(8000) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Derived/decoded identity type label.
      CUST_VAL_SGMNT_NME VARCHAR(200) CHARACTER SET LATIN NOT CASESPECIFIC,
      CUST_SECT_SGMNT_NME VARCHAR(200) CHARACTER SET LATIN NOT CASESPECIFIC,
      CUST_NAT_CD VARCHAR(200) CHARACTER SET UNICODE NOT CASESPECIFIC,
      CUST_GENDER_CD VARCHAR(200) CHARACTER SET UNICODE NOT CASESPECIFIC,
      CUST_BIRTH_DT VARCHAR(200) CHARACTER SET UNICODE NOT CASESPECIFIC,
      CUST_LANG_CD VARCHAR(200) CHARACTER SET UNICODE NOT CASESPECIFIC,
      PREVIOUS_RATEPLAN VARCHAR(100) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Rate plan immediately preceding the current product.
      -- Device, loyalty and activity recency.
      HANDSET_TYPE VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC,
      BRAND_MODEL VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC,
      TAMAYUZ_MEMBERSHIP_TYPE VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC,
      TAMAYUZ_PRIMARY_ACCOUNT BYTEINT,
      FIRST_USAGE_DATE DATE FORMAT 'YY/MM/DD',
      LAST_USAGE_DATE DATE FORMAT 'YY/MM/DD',
      LAST_ROAMING_DATE DATE FORMAT 'YY/MM/DD',
      FIRST_CALL_DATE DATE FORMAT 'YY/MM/DD',
      LAST_SMS_DATE DATE FORMAT 'YY/MM/DD',
      LAST_RECHARGE_DATE DATE FORMAT 'YY/MM/DD',
      LAST_DATA_DATE DATE FORMAT 'YY/MM/DD',
      LAST_CALL_ONNET_DATE DATE FORMAT 'YY/MM/DD',
      LAST_CALL_OFFNET_DATE DATE FORMAT 'YY/MM/DD',
      LAST_CALL_INT_DATE DATE FORMAT 'YY/MM/DD',
      LAST_CALL_DATE DATE FORMAT 'YY/MM/DD',
      -- Rolling revenue and outbound usage measures as of REF_DATE.
      LAST_MONTH_REV FLOAT DEFAULT 0.00000000000000E 000 ,
      LAST_3_MONTH_REV FLOAT DEFAULT 0.00000000000000E 000 ,
      LAST_6_MONTH_REV FLOAT DEFAULT 0.00000000000000E 000 ,
      MULTISIM BYTEINT DEFAULT 0 ,
      VOICE_PAYG_REV FLOAT DEFAULT 0.00000000000000E 000 ,
      VOICE_ONNET_REV FLOAT DEFAULT 0.00000000000000E 000 ,
      VOICE_OFFNET_REV FLOAT DEFAULT 0.00000000000000E 000 ,
      VOICE_INTL_REV FLOAT DEFAULT 0.00000000000000E 000 ,
      DATA_PAYG_REV FLOAT DEFAULT 0.00000000000000E 000 ,
      ROAM_PAYG_REV FLOAT DEFAULT 0.00000000000000E 000 ,
      VOICE_OUT_USAGE FLOAT DEFAULT 0.00000000000000E 000 ,
      VOICE_ONNET_OUT_USAGE FLOAT DEFAULT 0.00000000000000E 000 ,
      VOICE_OFFNET_OUT_USAGE FLOAT DEFAULT 0.00000000000000E 000 ,
      VOICE_INTL_OUT_USG FLOAT DEFAULT 0.00000000000000E 000 ,
      DATA_PAYG_USG FLOAT DEFAULT 0.00000000000000E 000 ,
      DATA_USG FLOAT DEFAULT 0.00000000000000E 000 ,
      ROAM_DATA_USG FLOAT DEFAULT 0.00000000000000E 000 ,
      ROAM_PAYG_DATA_USG FLOAT DEFAULT 0.00000000000000E 000 ,
      ROAM_UNDER_PACK_DATA_USG FLOAT DEFAULT 0.00000000000000E 000 ,
      -- Inferred location centroids by time window; latitude/longitude are sensitive.
      WEEKEND_LAT DECIMAL(18,6),
      WEEKEND_LON DECIMAL(18,6),
      WEEKDAY_LAT DECIMAL(18,6),
      WEEKDAY_LON DECIMAL(18,6),
      BIZ_HOUR_LAT DECIMAL(18,6),
      BIZ_HOUR_LON DECIMAL(18,6),
      NON_BIZ_HOUR_LAT DECIMAL(18,6),
      NON_BIZ_HOUR_LON DECIMAL(18,6),
      OVERALL_LAT FLOAT,
      OVERALL_LON FLOAT,
      Hayy_Name VARCHAR(100) CHARACTER SET LATIN NOT CASESPECIFIC,
      City_Name VARCHAR(100) CHARACTER SET LATIN NOT CASESPECIFIC,
      Governerate_Name VARCHAR(100) CHARACTER SET LATIN NOT CASESPECIFIC,
      Region_Name VARCHAR(100) CHARACTER SET LATIN NOT CASESPECIFIC,
      -- Inbound usage, recharge and complaints.
      MASLAHI BYTEINT DEFAULT 0 , -- STC program/segment indicator; exact business rule requires owner confirmation.
      VOICE_IN_USG INTEGER DEFAULT 0 ,
      VOICE_IN_ONNET_USG INTEGER DEFAULT 0 ,
      VOICE_IN_ZAIN_USG INTEGER DEFAULT 0 ,
      VOICE_IN_MOBILY_USG INTEGER DEFAULT 0 ,
      VOICE_IN_OTHER_USG INTEGER DEFAULT 0 ,
      LAST_6M_RECHARGE FLOAT DEFAULT 0.00000000000000E 000 ,
      LAST_3M_RECHARGE FLOAT DEFAULT 0.00000000000000E 000 ,
      LAST_1M_RECHARGE FLOAT DEFAULT 0.00000000000000E 000 ,
      MOST_COMPLAINT_TYPE VARCHAR(255) CHARACTER SET UNICODE NOT CASESPECIFIC,
      TOTAL_COMPLAINT_CNT INTEGER DEFAULT 0 ,
      BT_RECHARGE DECIMAL(18,4) DEFAULT 0.0000 , -- Recharge amount in the BT-coded channel; confirm whether BT means balance or bank transfer.
      ONLINE_RECHARGE DECIMAL(18,4) DEFAULT 0.0000 ,
      STCPAY_RECHARGE DECIMAL(18,4) DEFAULT 0.0000 ,
      VOUCHER_RECHARGE DECIMAL(18,4) DEFAULT 0.0000 ,
      OTHER_RECHARGE DECIMAL(18,4) DEFAULT 0.0000 ,
      -- Roaming usage, commercial revenue and behavioral features.
      VOICE_ROAM_IN_USG FLOAT DEFAULT 0.00000000000000E 000 ,
      VOICE_ROAM_IN_PAYG_USG FLOAT DEFAULT 0.00000000000000E 000 ,
      VOICE_ROAM_IN_UNDER_PACK_USG FLOAT DEFAULT 0.00000000000000E 000 ,
      VOICE_ROAM_OUT_USG FLOAT DEFAULT 0.00000000000000E 000 ,
      VOICE_ROAM_OUT_PAYG_USG FLOAT DEFAULT 0.00000000000000E 000 ,
      VOICE_ROAM_OUT_UNDER_PACK_USG FLOAT DEFAULT 0.00000000000000E 000 ,
      SHERIKATI BYTEINT DEFAULT 0 ,
      ATL_REV FLOAT DEFAULT 0.00000000000000E 000 ,
      BTL_REV FLOAT DEFAULT 0.00000000000000E 000 ,
      RG_FLAG BYTEINT DEFAULT 0 , -- Revenue-generating indicator; distinct from the 30-day RGS flag in other tables.
      ROAM_PACK_REV FLOAT DEFAULT 0.00000000000000E 000 ,
      DCB_REV FLOAT DEFAULT 0.00000000000000E 000 ,
      RECHARGE_FREQ FLOAT DEFAULT 0.00000000000000E 000 ,
      P_SEGMENT VARCHAR(2) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Prepaid/commercial segment code; confirm codebook.
      DEVICE_CONTRACT_FLAG BYTEINT DEFAULT 0 ,
      VBS VARCHAR(11) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Value-based segment (observed VHV, HV, MHV, MV, LV, VLV, NEW).
      VBS_BRACKET VARCHAR(11) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Revenue band behind VBS (for example 0-25, 25-50, 225+).
      AVG_REV_3M FLOAT DEFAULT 0.00000000000000E 000 ,
      ATL_USER_FLAG BYTEINT DEFAULT 0 , -- 1 when the line used/bought an ATL package in the feature window.
      BTL_USER_FLAG BYTEINT DEFAULT 0 , -- 1 when the line used/bought a BTL package in the feature window.
      BUNDLE_USER_FLAG BYTEINT DEFAULT 0 , -- 1 when any qualifying bundle was used/bought.
      CORE_TELECOM_ACTIVITY_FLAG BYTEINT DEFAULT 0 , -- 1 when qualifying core telecom activity exists.
      HIGHEST_ATL VARCHAR(255) CHARACTER SET LATIN NOT CASESPECIFIC, -- Highest-ranked/value ATL package in the feature window.
      HIGHEST_BTL VARCHAR(255) CHARACTER SET LATIN NOT CASESPECIFIC, -- Highest-ranked/value BTL package in the feature window.
      MOST_USED_RCHRG_CHL VARCHAR(255) CHARACTER SET LATIN NOT CASESPECIFIC, -- Dominant recharge channel.
      ACTIVE_30_FLAG BYTEINT DEFAULT 0 , -- Observed as 0/1; 30-day active-line indicator.
      LINE_TENURE VARCHAR(100) CHARACTER SET LATIN NOT CASESPECIFIC, -- Derived line-age band as of REF_DATE.
      AGE_B VARCHAR(100) CHARACTER SET LATIN NOT CASESPECIFIC, -- Customer age band (<=18, 18-25, 26-35, 36-55, >55, UNKNOWN).
      PREV_BRAND_MODEL VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC,
      NO_OF_PAYMENT_DELINQUENCY INTEGER DEFAULT 0 ,
      NEW_DEVICE_FLAG BYTEINT DEFAULT 0 ,
      NEW_MOVER BYTEINT DEFAULT 0 , -- Recent geographic mover indicator inferred from location history.
      TIMELINESS_OF_PAYMENT INTEGER,
      LIFESTYLE_SEGMENT VARCHAR(255) CHARACTER SET LATIN NOT CASESPECIFIC,
      FREQ_DROPPED_CALLS INTEGER DEFAULT 0 ,
      CALLS_TO_900 INTEGER DEFAULT 0 ,
      THROUGH_PUT FLOAT, -- Network data-throughput experience metric; confirm unit/aggregation.
      FUP BYTEINT DEFAULT 0 ) -- Fair Usage Policy indicator/trigger.
PRIMARY INDEX ( ACCS_METH_KEY ,ACCNT_KEY )
PARTITION BY RANGE_N(REF_DATE  BETWEEN DATE '2014-01-01' AND DATE '2030-12-31' EACH INTERVAL '1' MONTH )
INDEX IDX_F_MOBILITY_360_01 ( ACCS_METH_VAL ,ACCNT_NMBR ,LINE_TYPE )
INDEX ( REF_DATE ,ACCS_METH_VAL ,LINE_TYPE ,CUST_KEY )
INDEX ( CUST_IDENT_NUM );



/*
Table: DP_EDW_PPF.D_PP_PACKAGE
Purpose: Canonical prepaid package dimension for SAWA and QuickNet offers, with
         commercial taxonomy, validity, price and reporting bands.
Intended grain: one canonical package per PCKG_ID. PCKG_NAME is descriptive and
                not a safe key because names vary by case, spacing and duration.
Observed taxonomy: PCKG_TYPE = ATL/BTL; service = SAWA/Quicknet/UNK; validity unit
                   currently D (days); categories include Flex, Data, Voice,
                   International, Roaming, Visitor, Social and legacy SAWA families.
*/
CREATE SET TABLE DP_EDW_PPF.D_PP_PACKAGE ,FALLBACK ,
     NO BEFORE JOURNAL,
     NO AFTER JOURNAL,
     CHECKSUM = DEFAULT,
     DEFAULT MERGEBLOCKRATIO,
     MAP = TD_MAP3
     (
      PCKG_ID VARCHAR(50) CHARACTER SET UNICODE NOT CASESPECIFIC NOT NULL, -- Canonical package identifier and dimension key.
      PCKG_TYPE VARCHAR(30) CHARACTER SET LATIN NOT CASESPECIFIC NOT NULL, -- Marketing/revenue class: ATL or BTL.
      PCKG_SERVICE_TYPE VARCHAR(30) CHARACTER SET LATIN NOT CASESPECIFIC NOT NULL, -- Service family: SAWA, Quicknet or UNK.
      PCKG_NAME VARCHAR(255) CHARACTER SET UNICODE NOT CASESPECIFIC NOT NULL, -- Customer/commercial package name; Unicode supports Arabic names.
      PCKG_DESC VARCHAR(1000) CHARACTER SET UNICODE NOT CASESPECIFIC, -- Longer package description/benefit text.
      PCKG_CATEGORY VARCHAR(255) CHARACTER SET LATIN NOT CASESPECIFIC, -- Reporting category such as Flex, Data, Voice, Visitor or Roaming.
      PCKG_SUB_CATEGORY VARCHAR(255) CHARACTER SET LATIN NOT CASESPECIFIC, -- Duration/frequency grouping such as Daily, Weekly or Monthly.
      VALIDITY_DUR_TYPE VARCHAR(30) CHARACTER SET LATIN NOT CASESPECIFIC, -- Unit for VALIDITY_AMOUNT; observed D = days.
      VALIDITY_AMOUNT FLOAT, -- Package validity expressed in VALIDITY_DUR_TYPE units.
      PRICE FLOAT, -- Package list/face price, normally SAR; confirm tax treatment.
      PCKG_GROUP_1 VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC, -- Ordered reporting group combining family/type/price tier.
      PRICE_RANGE VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC) -- Standard price band from A. 0 through H. 250+, or NA.
PRIMARY INDEX ( PCKG_ID )
INDEX IDX_D_PP_PACKAGE_SIM_TYPE_01 ( PCKG_NAME );



/*
Table: DP_EDW_PPF.D_PP_PACKAGE_SRC_LKP
Purpose: Effective-dated crosswalk from source-system package codes/names to the
         canonical D_PP_PACKAGE.PCKG_ID, with SIM form factor and revenue capture.
Intended grain: one DATA_SOURCE_SYSTEM + SRC_SYS_CODE + REC_START_DT + REC_END_DT
                mapping. Date ranges should not overlap for the same source/code.
Observed values: SIM_TYPE = E-SIM/Physical SIM/NA; REV_CAPTURED_FLAG = Y/N;
                 source/subsystem labels include MySTC, EVD, gift, recharge,
                 renewal, sponsor, OLP and voucher channels.
*/
CREATE SET TABLE DP_EDW_PPF.D_PP_PACKAGE_SRC_LKP ,FALLBACK ,
     NO BEFORE JOURNAL,
     NO AFTER JOURNAL,
     CHECKSUM = DEFAULT,
     DEFAULT MERGEBLOCKRATIO,
     MAP = TD_MAP3
     (
      PCKG_ID VARCHAR(50) CHARACTER SET LATIN NOT CASESPECIFIC, -- Canonical package key joining to D_PP_PACKAGE.
      SIM_TYPE VARCHAR(100) CHARACTER SET LATIN NOT CASESPECIFIC, -- SIM form factor: E-SIM, Physical SIM or NA.
      DATA_SOURCE_SYSTEM VARCHAR(100) CHARACTER SET LATIN NOT CASESPECIFIC, -- Source platform/system owning SRC_SYS_CODE.
      DATA_SOURCE_SUB_SYSTEM VARCHAR(255) CHARACTER SET LATIN NOT CASESPECIFIC, -- Source flow/channel below the system level.
      SRC_SYS_CODE VARCHAR(255) CHARACTER SET LATIN NOT CASESPECIFIC, -- Source-native package/product code.
      REV_CAPTURED_FLAG VARCHAR(1) CHARACTER SET LATIN NOT CASESPECIFIC, -- Y when revenue is captured from this mapping/source flow.
      REC_START_DT DATE FORMAT 'yyyy-mm-dd', -- Effective-from date (inclusive unless source rules state otherwise).
      REC_END_DT DATE FORMAT 'yyyy-mm-dd', -- Effective-to date; confirm inclusive/exclusive convention.
      PRICE DECIMAL(12,6), -- Source-specific mapped price, normally SAR.
      OLD_PCKG_NAME VARCHAR(255) CHARACTER SET LATIN NOT CASESPECIFIC) -- Legacy/source package name retained for traceability.
PRIMARY INDEX ( DATA_SOURCE_SYSTEM ,SRC_SYS_CODE ,REC_START_DT ,
REC_END_DT )
INDEX IDX_D_PP_PACKAGE_SRC_LKP_01 ( PCKG_ID )
INDEX IDX_D_PP_PACKAGE_SRC_LKP_02 ( DATA_SOURCE_SUB_SYSTEM );





/*
View: DP_EDW_PPF_VEW.V_PP_RGS_CHURN_DLY
Purpose: Daily soft/explicit churn population. A line is emitted when it qualified
         as 30-day RGS on REF_DATE but no longer qualifies on the following day.
Intended grain: one CHURN_DATE + ROOT_SUBS_KEY.
Grain caveat: the QUALIFY deduplication is commented out. Multiple matching sales,
              churn or prior attribution rows can duplicate a subscriber/date.
              Use COUNT(DISTINCT ROOT_SUBS_KEY) until full-data uniqueness is proven.
Output semantics: CHURN_TYPE uses the service-order subtype when available and
                  defaults to RGS - Soft Churn; BUNDLE_TYPE rolls non-ATL/BTL RGS
                  lines into PayG; CORE_SEG derives from sales cohort and four-month
                  current-usage continuity.
Observed output: Daily Churn; ATL/BTL/PayG/Prorated Bundle Dormant; churn reasons
                 include customer/system initiated, MNP port-out, dunning,
                 ownership, prepaid migrations/transfers and soft churn.
*/
REPLACE VIEW DP_EDW_PPF_VEW.V_PP_RGS_CHURN_DLY AS
SELECT A30.REF_DATE + 1 CHURN_DATE,
	Cast('Daily Churn' AS VARCHAR(30)) CATEGORY, 
	CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
        WHEN CL.CUST_IDENT_SUB_TYP_NME = U&'    \062C\0648\0627\0632 \0633\06BA\0631 \0632\0627\0626\0631 \0648 \062F\0628\0644\0648\0645\0627\0633\064A\064A\0646 ' UESCAPE '\' THEN 'P' 
        ELSE 'Others' END ID_TYPE,
	CL.CUST_NAT_CD,
	A30.PROD_NME AS RATEPLAN,
	CASE WHEN RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
	CASE WHEN A30.RGS_30_FLAG = 'Y' THEN
		CASE WHEN A30.BUNDLE_TYPE IN ('ATL','BTL') THEN A30.BUNDLE_TYPE
			WHEN A30.BUNDLE_TYPE = 'Prorated Bundle Dormant' THEN 'Prorated Bundle Dormant'
			ELSE 'PayG' END ELSE 'NRGS' END BUNDLE_TYPE,
	Coalesce(FLC.ORDER_SUBTYP_NME,'RGS - Soft Churn') CHURN_TYPE,
	A30.CUST_KEY,
	A30.ROOT_SUBS_KEY,
	A30.ACCS_METH_KEY,
    CASE WHEN Coalesce(RA.SALES_COHORT_MONTH,'00') IN ('00','01','02') THEN 'New Sales' 
        WHEN Coalesce(RA.SALES_COHORT_MONTH,'00') NOT IN ('00','01','02') THEN
            CASE WHEN Coalesce(RA.CNT_LAST_4MS_CU,0) = 4 THEN 'Core Base'
                ELSE 'Non-Core Base' END 
        ELSE 'Undefined' END CORE_SEG
FROM (SELECT A.REF_DATE,
		A.ROOT_SUBS_KEY,
		A.ACCS_METH_KEY,
		A.CUST_KEY,
		A.RGS_30_FLAG,
		A.PROD_NME,
		A.BUNDLE_TYPE,
		Coalesce(FLS.FIRST_RG_DATE,DATE '1900-01-01') FRG
	FROM DP_EDW_PPF.F_PP_DAILY_ACTIVE_30 A
		LEFT OUTER JOIN DP_EDW_PPF.F_LINE_SALES FLS ON (FLS.ROOT_SUBS_KEY = A.ROOT_SUBS_KEY)) A30
	INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = A30.CUST_KEY)
	LEFT OUTER JOIN DP_EDW_PPF.F_LINE_CHURN FLC ON (FLC.ROOT_SUBS_KEY = A30.ROOT_SUBS_KEY
		AND FLC.ORDER_END_DT = A30.REF_DATE + 1
		--AND FLC.CHURN_FLAG = 'Churn'
		)
	LEFT OUTER JOIN DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RA ON (RA.ROOT_SUBS_KEY = A30.ROOT_SUBS_KEY
			AND RA.REF_DATE = Trunc(CHURN_DATE,'MM')-1
			AND RA.MNTHLY_WKLY_FLAG = 'M'
			AND RA.RGS_30_FLAG = 'Y')
WHERE A30.RGS_30_FLAG = 'Y'
	AND Trunc(A30.FRG,'MM') <> Trunc(CHURN_DATE,'MM')
	AND A30.REF_DATE < (SELECT Max(REF_DATE) FROM DP_EDW_PPF.F_PP_DAILY_ACTIVE_30 )
	AND NOT EXISTS (SELECT ROOT_SUBS_KEY
					FROM DP_EDW_PPF.F_PP_DAILY_ACTIVE_30 A30N
					WHERE A30N.ROOT_SUBS_KEY = A30.ROOT_SUBS_KEY
						AND A30N.REF_DATE = A30.REF_DATE + 1
						AND A30N.RGS_30_FLAG = 'Y')
--QUALIFY Row_Number() Over(PARTITION BY A30.REF_DATE, A30.ROOT_SUBS_KEY ORDER BY FLC.ORDER_END_DT DESC, RA.REF_DATE DESC) = 1;;; 





/*
View: DP_EDW_PPF_VEW.V_PP_RGS_CHURN_MTHLY
Purpose: Month-end RGS churn population. It selects period-end active 30-day RGS
         lines that are absent from the next monthly RGS snapshot.
Intended grain: one MONTH_END_DATE + ROOT_SUBS_KEY.
Grain caveat: multiple F_LINE_CHURN matches for the same line/month can duplicate
              rows because no QUALIFY is applied.
Key derivations: CORE_SEG = New Sales for cohorts 00-02, otherwise Core Base when
                 CNT_LAST_4MS_CU = 4; VBS is a TOTAL_REV band for SCREEN_TYPE SS;
                 LINE_TENURE is derived from REF_DATE minus LINE_START_DATE.
Boundary note: the VBS BETWEEN conditions overlap at 25, 50, 106, 160 and 225;
               CASE order assigns boundary values to the earlier/lower-value band.
*/
REPLACE VIEW DP_EDW_PPF_VEW.V_PP_RGS_CHURN_MTHLY AS
SELECT Last_Day(RA.REF_DATE + 1) MONTH_END_DATE,
	Cast('Monthly Churn' AS VARCHAR(30)) CATEGORY,
	RA.SCREEN_TYPE,
	CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
        WHEN CL.CUST_IDENT_SUB_TYP_NME = U&'    \062C\0648\0627\0632 \0633\06BA\0631 \0632\0627\0626\0631 \0648 \062F\0628\0644\0648\0645\0627\0633\064A\064A\0646 ' UESCAPE '\' THEN 'P' 
        ELSE 'Others' END ID_TYPE,
	CL.CUST_NAT_CD,
	RA.RATEPLAN,
	RA.LINE_START_DATE,
    CASE WHEN RA.SALES_COHORT_MONTH = 'OLDER' THEN 'OLDER'
    	WHEN Cast(RA.SALES_COHORT_MONTH AS INTEGER) >= 11 THEN 'OLDER'
    	ELSE LPad(Cast(Cast(RA.SALES_COHORT_MONTH AS INTEGER) + 1 AS VARCHAR(2)), 2, '0')
	END SALES_COHORT_MONTH_,
	RA.CNT_LAST_4MS_CU,
	CASE WHEN RA.SALES_COHORT_MONTH IN ('00','01','02') THEN 'New Sales' 
		WHEN RA.SALES_COHORT_MONTH NOT IN ('00','01','02') THEN
			CASE WHEN RA.CNT_LAST_4MS_CU = 4 THEN 'Core Base'
				ELSE 'Non-Core Base' END 
		ELSE '????' END CORE_SEG,
	RA.OWNERSHIP_CHANGE_FLAG,
	CASE WHEN RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
	Coalesce(FLC.ORDER_SUBTYP_NME,'RGS Soft Churn') CHURN_TYPE,
	CASE WHEN RA.RGS_30_FLAG = 'Y' THEN
		CASE WHEN RA.BUNDLE_TYPE IN ('ATL','BTL','PG Telcom','DCB VAS') THEN RA.BUNDLE_TYPE
			WHEN RA.BUNDLE_TYPE = 'Prorated Bundle Dormant' THEN 'Prorated Bundle Dormant'
			ELSE 'Unknown' END ELSE 'NRGS' END BUNDLE_TYPE,
    CASE WHEN RA.SCREEN_TYPE = 'SS' THEN
        CASE WHEN  Coalesce(RA.TOTAL_REV,0)  <= 25  THEN '6. VLV (0-25)'
                WHEN Coalesce(RA.TOTAL_REV,0) BETWEEN 25 AND 50 THEN '5. LV (25-50)'
                WHEN Coalesce(RA.TOTAL_REV,0) BETWEEN 50 AND 106  THEN '4. MV (50-106)'
                WHEN Coalesce(RA.TOTAL_REV,0) BETWEEN 106 AND 160  THEN '3. MHVB (106-160)'
                WHEN Coalesce(RA.TOTAL_REV,0) BETWEEN 160 AND 225  THEN '2. HV (160-225)'
                WHEN Coalesce(RA.TOTAL_REV,0) > 225 THEN '1. VHV (>225)' END
        ELSE 'NA' END AS VBS,
    CASE WHEN Cast(RA.REF_DATE - Cast(RA.LINE_START_DATE AS DATE) AS INTEGER) < 90 THEN '1. < 3M'
        WHEN Cast(RA.REF_DATE - Cast(RA.LINE_START_DATE AS DATE) AS INTEGER) BETWEEN 90 AND 180 THEN '2. 3-6M'
        WHEN Cast(RA.REF_DATE - Cast(RA.LINE_START_DATE AS DATE) AS INTEGER) BETWEEN 180 AND 360 THEN '3. 6M-12M'
        WHEN Cast(RA.REF_DATE - Cast(RA.LINE_START_DATE AS DATE) AS INTEGER) BETWEEN 360 AND 1080 THEN '4. 1Y-3Y'
        WHEN Cast(RA.REF_DATE - Cast(RA.LINE_START_DATE AS DATE) AS INTEGER) BETWEEN 1080 AND 1800 THEN '5. 3Y-5Y'
        ELSE  '6. > 5Y' END LINE_TENURE,
	RA.CUST_KEY,
	RA.ROOT_SUBS_KEY,
	RA.TOTAL_REV
FROM DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RA
	INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = RA.CUST_KEY)
	LEFT OUTER JOIN DP_EDW_PPF.F_LINE_CHURN FLC ON (FLC.ROOT_SUBS_KEY = RA.ROOT_SUBS_KEY
				AND Last_Day(FLC.ORDER_END_DT) = Last_Day(RA.REF_DATE + 1)
				--AND FLC.CHURN_FLAG = 'Churn'
				)
WHERE RA.PERIOD_END_ACT_FLAG = 'Y'
	--AND RA.SCREEN_TYPE = 'SS'
	AND RA.RGS_30_FLAG = 'Y'
	AND RA.MNTHLY_WKLY_FLAG = 'M'
	AND RA.REF_DATE < (SELECT Max(REF_DATE) 
						FROM DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION 
						WHERE MNTHLY_WKLY_FLAG = 'M') 
	AND NOT EXISTS (SELECT RAN.ROOT_SUBS_KEY
					FROM DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RAN
					WHERE RAN.REF_DATE = Last_Day(RA.REF_DATE + 1)
						AND RAN.ROOT_SUBS_KEY = RA.ROOT_SUBS_KEY
						AND RAN.RGS_30_FLAG = 'Y'
						AND RAN.MNTHLY_WKLY_FLAG = 'M'
						AND RAN.PERIOD_END_ACT_FLAG = 'Y'); 




/*
View: DP_EDW_PPF_VEW.V_PP_RGS_RECONNECT_DLY
Purpose: Daily reconnect population. A line is emitted when it qualifies as 30-day
         RGS today, did not qualify yesterday, and is not a same-day new sale.
Enforced output grain: one RECONNECT_DATE + ROOT_SUBS_KEY via QUALIFY ROW_NUMBER.
Output semantics: RECONNECT_TYPE uses a non-sale service-order subtype where found
                  and defaults to RGS - Reconnect; BUNDLE_TYPE is ATL, BTL, PayG or
                  Prorated Bundle Dormant; Ziyara-named plans form the visitor flag.
Observed reconnect types: Ownership, PrepaidtoPrepaid, Transfer and RGS - Reconnect.
*/
REPLACE VIEW DP_EDW_PPF_VEW.V_PP_RGS_RECONNECT_DLY AS
SELECT A30.REF_DATE RECONNECT_DATE,
	Cast('Daily Reconnects' AS VARCHAR(30)) CATEGORY, 
	Coalesce(FLSRT.ORDER_SUBTYP_NME,'RGS - Reconnect') RECONNECT_TYPE,
	CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
        WHEN CL.CUST_IDENT_SUB_TYP_NME = U&'    \062C\0648\0627\0632 \0633\06BA\0631 \0632\0627\0626\0631 \0648 \062F\0628\0644\0648\0645\0627\0633\064A\064A\0646 ' UESCAPE '\' THEN 'P' 
        ELSE 'Others' END ID_TYPE,
	CL.CUST_NAT_CD,
	A30.PROD_NME AS RATEPLAN,
	CASE WHEN RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
	CASE WHEN A30.RGS_30_FLAG = 'Y' THEN
	CASE WHEN A30.BUNDLE_TYPE IN ('ATL','BTL') THEN A30.BUNDLE_TYPE
		WHEN A30.BUNDLE_TYPE = 'Prorated Bundle Dormant' THEN 'Prorated Bundle Dormant'
		ELSE 'PayG' END ELSE 'NRGS' END BUNDLE_TYPE,
	A30.CUST_KEY,
	A30.ROOT_SUBS_KEY,
	A30.ACCS_METH_KEY,
    CASE WHEN Coalesce(RA.SALES_COHORT_MONTH,'00') IN ('00','01','02') THEN 'New Sales' 
        WHEN Coalesce(RA.SALES_COHORT_MONTH,'00') NOT IN ('00','01','02') THEN
            CASE WHEN Coalesce(RA.CNT_LAST_4MS_CU,0) = 4 THEN 'Core Base'
                ELSE 'Non-Core Base' END 
        ELSE 'Undefined' END CORE_SEG
FROM DP_EDW_PPF.F_PP_DAILY_ACTIVE_30 A30
	INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = A30.CUST_KEY)
	LEFT OUTER JOIN DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RA ON (RA.ROOT_SUBS_KEY = A30.ROOT_SUBS_KEY
			AND RA.REF_DATE <= Trunc(A30.REF_DATE,'MM')-1
			AND RA.MNTHLY_WKLY_FLAG = 'M'
			AND RA.RGS_30_FLAG = 'Y')
	LEFT OUTER JOIN DP_EDW_PPF.F_LINE_SALES FLSRT ON (FLSRT.ROOT_SUBS_KEY = A30.ROOT_SUBS_KEY
			AND FLSRT.FIRST_RG_DATE = A30.REF_DATE
			AND FLSRT.SALES_FLAG <> 'Sales')
WHERE A30.RGS_30_FLAG = 'Y'
	AND A30.REF_DATE > (SELECT Min(REF_DATE) FROM DP_EDW_PPF.F_PP_DAILY_ACTIVE_30) 
	AND NOT EXISTS (SELECT ROOT_SUBS_KEY
					FROM DP_EDW_PPF.F_PP_DAILY_ACTIVE_30 A30P
					WHERE A30P.ROOT_SUBS_KEY = A30.ROOT_SUBS_KEY
						AND A30P.REF_DATE = A30.REF_DATE - 1
						AND A30P.RGS_30_FLAG = 'Y')
	AND NOT EXISTS (SELECT FLS.ROOT_SUBS_KEY
					FROM DP_EDW_PPF.F_LINE_SALES FLS
					WHERE FLS.FIRST_RG_DATE = A30.REF_DATE
						AND FLS.ROOT_SUBS_KEY = A30.ROOT_SUBS_KEY
						AND FLS.SALES_FLAG = 'Sales')
QUALIFY Row_Number() Over(PARTITION BY A30.REF_DATE, A30.ROOT_SUBS_KEY ORDER BY RA.REF_DATE DESC) = 1; 






/*
View: DP_EDW_PPF_VEW.V_PP_RGS_RECONNET_MTHLY
Purpose: Month-end reconnect population. It selects SS lines that are active 30-day
         RGS at the current month end, absent at the prior month end and not new
         sales in the current month.
Intended grain: one MONTH_END_DATE + ROOT_SUBS_KEY.
Grain caveat: multiple matching non-sale F_LINE_SALES rows can duplicate a line/month.
Naming note: RECONNET is the existing database object spelling (missing the second C
             in RECONNECT); retain it in dependencies unless the object is migrated.
Observed output: CATEGORY = Monthly Reconnect; SCREEN_TYPE = SS; bundle classes are
                 ATL, BTL, PG Telcom, Prorated Bundle Dormant or Unknown; VBS and
                 LINE_TENURE use the documented monthly bands.
*/
REPLACE VIEW DP_EDW_PPF_VEW.V_PP_RGS_RECONNET_MTHLY AS
SELECT RA.REF_DATE MONTH_END_DATE,
	Cast('Monthly Reconnect' AS VARCHAR(30)) CATEGORY,
	Coalesce(FLSRT.ORDER_SUBTYP_NME,'RGS - Reconnect') RECONNECT_TYPE,
	RA.SCREEN_TYPE,
	CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
        WHEN CL.CUST_IDENT_SUB_TYP_NME = U&'    \062C\0648\0627\0632 \0633\06BA\0631 \0632\0627\0626\0631 \0648 \062F\0628\0644\0648\0645\0627\0633\064A\064A\0646 ' UESCAPE '\' THEN 'P' 
        ELSE 'Others' END ID_TYPE,
	CL.CUST_NAT_CD,
	RA.RATEPLAN,
	CASE WHEN RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
	CASE WHEN RA.RGS_30_FLAG = 'Y' THEN
		CASE WHEN RA.BUNDLE_TYPE IN ('ATL','BTL','PG Telcom','DCB VAS') THEN RA.BUNDLE_TYPE
			WHEN RA.BUNDLE_TYPE = 'Prorated Bundle Dormant' THEN 'Prorated Bundle Dormant'
			ELSE 'Unknown' END ELSE 'NRGS' END BUNDLE_TYPE,
	CASE WHEN RA.SALES_COHORT_MONTH IN ('00','01','02') THEN 'New Sales' 
		WHEN RA.SALES_COHORT_MONTH NOT IN ('00','01','02') THEN
			CASE WHEN RA.CNT_LAST_4MS_CU = 4 THEN 'Core Base'
				ELSE 'Non-Core Base' END 
		ELSE '????' END CORE_SEG,
    CASE WHEN RA.SCREEN_TYPE = 'SS' THEN
        CASE WHEN  Coalesce(RA.TOTAL_REV,0)  <= 25  THEN '6. VLV (0-25)'
                WHEN Coalesce(RA.TOTAL_REV,0) BETWEEN 25 AND 50 THEN '5. LV (25-50)'
                WHEN Coalesce(RA.TOTAL_REV,0) BETWEEN 50 AND 106  THEN '4. MV (50-106)'
                WHEN Coalesce(RA.TOTAL_REV,0) BETWEEN 106 AND 160  THEN '3. MHVB (106-160)'
                WHEN Coalesce(RA.TOTAL_REV,0) BETWEEN 160 AND 225  THEN '2. HV (160-225)'
                WHEN Coalesce(RA.TOTAL_REV,0) > 225 THEN '1. VHV (>225)' END
        ELSE 'NA' END AS VBS,
    CASE WHEN Cast(RA.REF_DATE - Cast(RA.LINE_START_DATE AS DATE) AS INTEGER) < 90 THEN '1. < 3M'
        WHEN Cast(RA.REF_DATE - Cast(RA.LINE_START_DATE AS DATE) AS INTEGER) BETWEEN 90 AND 180 THEN '2. 3-6M'
        WHEN Cast(RA.REF_DATE - Cast(RA.LINE_START_DATE AS DATE) AS INTEGER) BETWEEN 180 AND 360 THEN '3. 6M-12M'
        WHEN Cast(RA.REF_DATE - Cast(RA.LINE_START_DATE AS DATE) AS INTEGER) BETWEEN 360 AND 1080 THEN '4. 1Y-3Y'
        WHEN Cast(RA.REF_DATE - Cast(RA.LINE_START_DATE AS DATE) AS INTEGER) BETWEEN 1080 AND 1800 THEN '5. 3Y-5Y'
        ELSE  '6. > 5Y' END LINE_TENURE,
	RA.CUST_KEY,
	RA.ROOT_SUBS_KEY,
	RA.TOTAL_REV
FROM DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RA
	INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = RA.CUST_KEY)
	LEFT OUTER JOIN DP_EDW_PPF.F_LINE_SALES FLSRT ON (FLSRT.ROOT_SUBS_KEY = RA.ROOT_SUBS_KEY
			AND Last_Day(FLSRT.FIRST_RG_DATE) = RA.REF_DATE
			AND FLSRT.SALES_FLAG <> 'Sales')
WHERE RA.PERIOD_END_ACT_FLAG = 'Y'
	AND RA.SCREEN_TYPE = 'SS'
	AND RA.RGS_30_FLAG = 'Y'
	AND RA.MNTHLY_WKLY_FLAG = 'M'
	AND RA.REF_DATE > (SELECT Min(REF_DATE) 
						FROM DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION 
						WHERE MNTHLY_WKLY_FLAG = 'M') 
	AND NOT EXISTS (SELECT RAP.ROOT_SUBS_KEY
					FROM DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RAP
					WHERE RAP.REF_DATE = Trunc(RA.REF_DATE,'MM') - 1
						AND RAP.ROOT_SUBS_KEY = RA.ROOT_SUBS_KEY
						AND RAP.RGS_30_FLAG = 'Y'
						AND RAP.MNTHLY_WKLY_FLAG = 'M'
						AND RAP.PERIOD_END_ACT_FLAG = 'Y')
	AND NOT EXISTS (SELECT ROOT_SUBS_KEY
					FROM DP_EDW_PPF.F_LINE_SALES FLS
					WHERE FLS.ROOT_SUBS_KEY = RA.ROOT_SUBS_KEY
						AND Last_Day(FLS.FIRST_RG_DATE) = RA.REF_DATE
						AND FLS.SALES_FLAG = 'Sales');








--V_PP_BASE_DAILY_AGG

Context

This query creates an aggregated subscriber reporting dataset.

It combines:

Recent daily subscriber data.
Historical monthly data for comparison.
Customer and subscriber attributes such as Active 30, RGS, bundle, rate plan, nationality, ID type, and customer segment.

It counts subscribers (SUBS) by date and these dimensions, and adds calendar information such as month, week, MTD, fixed MTD, and month-end indicators.

The date logic is mainly used to get:

Recent data from the last few months.
The same completed month from the previous year.
MTD and month-end reporting dates.

--SQL QUERY
SELECT X.REF_DATE,
    CW.LST_DAY_OF_MTH,
	CW.LST_DAY_OF_WK,
	CW.CBU_MONTH_ID,
    CW.CBU_WEEK_ID,
    CW.CBU_MONTH_NUM,
	CW.CBU_WEEK_NUM,
    CW.day_of_month,
	CW.Day_Of_WEEK,
	CASE WHEN CW.day_of_month <= Extract(DAY From DATE - 1) THEN 'Y' ELSE 'N' END MTD_FLAG, 
	CASE WHEN CW.day_of_month = Extract(DAY From DATE - 1) THEN 'Y' ELSE 'N' END FIXED_MTD_FLAG, -- Fixed one Day 
	CASE WHEN CW.LST_Day_Of_MTH = CW.calendar_date THEN CW.calendar_date
 			WHEN CW.calendar_date = (SELECT Max(REF_DATE) FROM DP_EDW_PPF.F_PP_DAILY_ACTIVE_30 
									WHERE REF_DATE BETWEEN DATE - 5 AND DATE) THEN CW.calendar_date ELSE NULL END Month_End_DT,
	X.ACTIVE_30, X.RGS_30, X.RGS_1D, X.BUNDLE_TYPE, X.PCKG_WL_TYPE,
	X.RATEPLAN, X.ID_TYPE, X.NATIONALITY, X.DOMESTIC_SUBS_FLAG, X.CORE_SEG,X.SUBS
FROM
	(SELECT A30.REF_DATE,
	    CASE WHEN A30.ACTIVE_30_FLAG = 'Y' THEN 'Active 30' ELSE 'Inactive 30' END ACTIVE_30,
	    CASE WHEN A30.RGS_30_FLAG = 'Y' THEN 'RGS' ELSE 'NRGS' END RGS_30,
		CASE WHEN A30.RGS_1D_FLAG = 'Y' THEN 'RGS 1D' ELSE 'NRGS 1D' END RGS_1D,
		CASE WHEN A30.RGS_30_FLAG = 'Y' THEN
			CASE WHEN A30.BUNDLE_TYPE IN ('ATL','BTL','Prorated Bundle Dormant') THEN A30.BUNDLE_TYPE
				ELSE 'PayG' END ELSE 'NRGS' END BUNDLE_TYPE,
		Coalesce(A30.WL_BUNDLE_TYPE,'PAYG') PCKG_WL_TYPE,
	    A30.PROD_NME AS RATEPLAN,
	    CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
	        WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P' 
	        ELSE 'Others' END ID_TYPE,
	    CASE WHEN ID_TYPE = 'S' THEN 'Saudi' ELSE
	        CASE WHEN CL.CUST_NAT_CD IN ('Yemen','Bangladesh','India','Pakistan','Sudan',
	            'Egypt','Philippines','Syria','Ethiopia','Indonesia','Nepal') THEN CL.CUST_NAT_CD ELSE 'Other' END END NATIONALITY,
		CASE WHEN A30.PROD_NME LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
	    CASE WHEN Coalesce(RA.SALES_COHORT_MONTH,'00') IN ('00','01','02') THEN 'New Sales' 
	        WHEN Coalesce(RA.SALES_COHORT_MONTH,'00') NOT IN ('00','01','02') THEN
	            CASE WHEN Coalesce(RA.CNT_LAST_4MS_CU,0) = 4 THEN 'Core Base'
	                ELSE 'Non-Core Base' END 
	        ELSE 'Undefined' END CORE_SEG,
	    Count(1) SUBS
	FROM DP_EDW_PPF.F_PP_DAILY_ACTIVE_30 A30
	    INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = A30.CUST_KEY)
		LEFT OUTER JOIN DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RA ON (RA.ROOT_SUBS_KEY = A30.ROOT_SUBS_KEY
				AND RA.REF_DATE = Trunc(A30.REF_DATE, 'MM')-1
				AND RA.MNTHLY_WKLY_FLAG = 'M'
				AND RA.REF_DATE >= Add_Months(Trunc(DATE - 3 ,'MM'),-3) - 1)
	WHERE A30.REF_DATE >= Add_Months(Trunc(DATE - 3 ,'MM'),-3)
	GROUP BY 1,2,3,4,5,6,7,8,9,10,11
	UNION
	SELECT RA.REF_DATE,
	    CASE WHEN ACTIVE_30_FLAG = 'Y' THEN 'Active 30' ELSE 'Inactive 30' END ACTIVE_30,
	    CASE WHEN RGS_30_FLAG = 'Y' THEN 'RGS' ELSE 'NRGS' END RGS_30,
		'NA' AS RGS_1D,
		CASE WHEN RGS_30_FLAG = 'Y' THEN
			CASE WHEN BUNDLE_TYPE IN ('ATL','BTL','Prorated Bundle Dormant') THEN BUNDLE_TYPE
				ELSE 'PayG' END ELSE 'NRGS' END BUNDLE_TYPE,
		'NA' PCKG_WL_TYPE,
	    RA.RATEPLAN,
	    CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
	        WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P' 
	        ELSE 'Others' END ID_TYPE,
	    CASE WHEN ID_TYPE = 'S' THEN 'Saudi' ELSE
	        CASE WHEN CL.CUST_NAT_CD IN ('Yemen','Bangladesh','India','Pakistan','Sudan',
	            'Egypt','Philippines','Syria','Ethiopia','Indonesia','Nepal') THEN CL.CUST_NAT_CD ELSE 'Other' END END NATIONALITY,
		CASE WHEN RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
		   CASE WHEN Coalesce(RA.SALES_COHORT_MONTH,'00') IN ('00','01','02') THEN 'New Sales' 
	        WHEN Coalesce(RA.SALES_COHORT_MONTH,'00') NOT IN ('00','01','02') THEN
	            CASE WHEN Coalesce(RA.CNT_LAST_4MS_CU,0) = 4 THEN 'Core Base'
	                ELSE 'Non-Core Base' END 
	        ELSE 'Undefined' END CORE_SEG, 
	    Count(1) SUBS
	FROM DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RA
	    INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = RA.CUST_KEY)
	WHERE RA.REF_DATE BETWEEN Add_Months(Trunc(DATE - 2,'MM'),-12) AND Add_Months(Trunc(DATE - 2,'MM'),-11) - 1
		AND RA.MNTHLY_WKLY_FLAG = 'M'
		AND RA.PERIOD_END_ACT_FLAG = 'Y'
		AND RA.SCREEN_TYPE = 'SS'
		AND (RA.RGS_30_FLAG = 'Y' OR RA.ACTIVE_30_FLAG = 'Y')
	GROUP BY 1,2,3,4,5,6,7,8,9,10,11)X
    INNER JOIN DP_EDW_PPF.CBU_Weeks CW ON (CW.calendar_date = X.REF_DATE);
	
	


--V_PP_DASH_SALES
Context

This query is a Prepaid Sales and Customer Lifecycle report.

It takes prepaid sales from the last 18 completed months, classifies customers by package, nationality, age, channel, SIM type, MNP, OLP, etc., and counts the sales.

It then tracks those sold customers for 12 months after the sale (M0–M11) to measure:

RGS 30
Active 30
Revenue

The output is aggregated by sales date and customer/sales dimensions for sales performance and customer lifecycle analysis.

--SQL QUERY
SELECT FLS.ORDER_END_DT SALES_DATE,
    CW.year_of_calendar YEAR_,
    Cast(Cast(day_of_month AS FORMAT'-9(2)') AS CHAR(2)) DAY_OF_MNTH,
    CASE WHEN Month_of_Year < Extract(MONTH From DATE-1) THEN 'Y' ELSE 'N' END YTM_Flag,
    CW.CBU_WEEK_ID,
    CW.CBU_MONTH_ID,
    CW.LST_DAY_OF_MTH,
    CW.LST_DAY_OF_WK,
    CASE WHEN CW.day_of_month <= Extract(DAY From DATE - 1) THEN 'Y' ELSE 'N' END MTD_FLAG,
    FLS.ORDER_SUBTYP_NME AS SALES_TYPE,
    FLS.SCREEN_TYPE,
    CASE WHEN FLS.SCREEN_TYPE  = 'SS' THEN 
        CASE WHEN FLS.RATE_PLAN_NME LIKE '%Ziyara%' THEN 'Ziyarah'
            WHEN FLS.RATE_PLAN_NME = 'SAWA Postpaid' THEN 'SAWA Postpaid'
            WHEN FLS.RATE_PLAN_NME = 'Prepaid Voice SAWA Workers' THEN 'SAWA Workers'
            ELSE 'SAWA Regular' END
        ELSE FLS.RATE_PLAN_NME END AS PACKAGE,
    CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
        WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P' 
        ELSE 'Others' END ID_TYPE,
    CASE WHEN FLS.RATE_PLAN_NME LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
    CASE WHEN CL.CUST_IDENT_SUB_TYP_NME = 'S' THEN 'Saudi' ELSE 'Non-Saudi' END SAUDI_FLAG,
    CASE WHEN CL.CUST_NAT_CD IS NULL THEN 'UNKNOWN'
    WHEN CL.CUST_NAT_CD LIKE '%SAUDI%' THEN 'Saudi' 
    WHEN CL.CUST_NAT_CD IN ('Yemen','Bangladesh','India','Pakistan','Sudan',
    'Egypt','Philippines','Syria','Ethiopia','Indonesia','Nepal') THEN CL.CUST_NAT_CD ELSE 'Other' END NATIONALITY,
    CASE WHEN CUST_BIRTH_DT <> 'UNKNOWN' THEN
    CASE WHEN Round(Cast(FLS.ORDER_END_DT - Cast(CUST_BIRTH_DT AS DATE) AS INTEGER)/365.00) <= 18 THEN '1. <= 18'
        WHEN Round(Cast(FLS.ORDER_END_DT - Cast(CUST_BIRTH_DT AS DATE) AS INTEGER)/365.00) BETWEEN 18 AND 25 THEN '2. 18 - 25'
        WHEN Round(Cast(FLS.ORDER_END_DT - Cast(CUST_BIRTH_DT AS DATE) AS INTEGER)/365.00) BETWEEN 25 AND 35 THEN '3. 26 - 35'
        WHEN Round(Cast(FLS.ORDER_END_DT - Cast(CUST_BIRTH_DT AS DATE) AS INTEGER)/365.00) BETWEEN 35 AND 55 THEN '4. 36 - 55'
        ELSE '5. > 55' END 
        ELSE 'UNKNOWN' END CUSTOMER_AGE_BRACKET,
    CASE WHEN LSA.CHANNEL = 'FieldSales' THEN 'Field Sales' ELSE Coalesce(InitCap(LSA.CHANNEL),'NA') END SALES_CHANNEL,
    Coalesce(InitCap(LSA.SUB_CHANNEL),'NA')  AS SALES_SUB_CHANNEL,
    CASE WHEN LSA.SIM_TYPE IS NOT NULL THEN 'E-SIM' ELSE 'ONP SIM' END SIM_TYPE,
    CASE WHEN FLS.ORDER_SUBTYP_NME LIKE '%MNP%' THEN Coalesce(LSA.MNP_FROM_OPR,'Unknown') ELSE 'NA' END AS  FROM_OPERATOR, 
    CASE WHEN LSA.OLP_PCKG IS NULL THEN 'Non_OLP' ELSE 'OLP' END OLP_Flag, 
    Coalesce(PP.PCKG_NAME,'NA') AS OLP_PACKAGE,
    CASE WHEN LSA.FIRST_USAGE_DATE IS NOT NULL THEN 'Y' ELSE 'N' END FIRST_USAGE,
    Count(DISTINCT FLS.SERVICE_ORDER_NUM) SALES,
    Sum(PP.PRICE) OLP_PCKG_PRICE,
    
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 0 AND RA.RGS_30_FLAG =  'Y' THEN 1 ELSE 0 END) M0_RGS_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 1 AND RA.RGS_30_FLAG =  'Y' THEN 1 ELSE 0 END) M1_RGS_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 2 AND RA.RGS_30_FLAG =  'Y' THEN 1 ELSE 0 END) M2_RGS_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 3 AND RA.RGS_30_FLAG =  'Y' THEN 1 ELSE 0 END) M3_RGS_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 4 AND RA.RGS_30_FLAG =  'Y' THEN 1 ELSE 0 END) M4_RGS_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 5 AND RA.RGS_30_FLAG =  'Y' THEN 1 ELSE 0 END) M5_RGS_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 6 AND RA.RGS_30_FLAG =  'Y' THEN 1 ELSE 0 END) M6_RGS_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 7 AND RA.RGS_30_FLAG =  'Y' THEN 1 ELSE 0 END) M7_RGS_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 8 AND RA.RGS_30_FLAG =  'Y' THEN 1 ELSE 0 END) M8_RGS_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 9 AND RA.RGS_30_FLAG =  'Y' THEN 1 ELSE 0 END) M9_RGS_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 10 AND RA.RGS_30_FLAG =  'Y' THEN 1 ELSE 0 END) M10_RGS_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 11 AND RA.RGS_30_FLAG =  'Y' THEN 1 ELSE 0 END) M11_RGS_30,

    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 0 AND RA.ACTIVE_30_FLAG =  'Y' THEN 1 ELSE 0 END) M0_ACTIVE_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 1 AND RA.ACTIVE_30_FLAG =  'Y' THEN 1 ELSE 0 END) M1_ACTIVE_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 2 AND RA.ACTIVE_30_FLAG =  'Y' THEN 1 ELSE 0 END) M2_ACTIVE_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 3 AND RA.ACTIVE_30_FLAG =  'Y' THEN 1 ELSE 0 END) M3_ACTIVE_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 4 AND RA.ACTIVE_30_FLAG =  'Y' THEN 1 ELSE 0 END) M4_ACTIVE_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 5 AND RA.ACTIVE_30_FLAG =  'Y' THEN 1 ELSE 0 END) M5_ACTIVE_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 6 AND RA.ACTIVE_30_FLAG =  'Y' THEN 1 ELSE 0 END) M6_ACTIVE_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 7 AND RA.ACTIVE_30_FLAG =  'Y' THEN 1 ELSE 0 END) M7_ACTIVE_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 8 AND RA.ACTIVE_30_FLAG =  'Y' THEN 1 ELSE 0 END) M8_ACTIVE_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 9 AND RA.ACTIVE_30_FLAG =  'Y' THEN 1 ELSE 0 END) M9_ACTIVE_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 10 AND RA.ACTIVE_30_FLAG =  'Y' THEN 1 ELSE 0 END) M10_ACTIVE_30,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 11 AND RA.ACTIVE_30_FLAG =  'Y' THEN 1 ELSE 0 END) M11_ACTIVE_30,

    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 0 THEN Coalesce(RA.TOTAL_REV,0) ELSE 0 END) M0_REV,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 1 THEN Coalesce(RA.TOTAL_REV,0) ELSE 0 END) M1_REV,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 2 THEN Coalesce(RA.TOTAL_REV,0) ELSE 0 END) M2_REV,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 3 THEN Coalesce(RA.TOTAL_REV,0) ELSE 0 END) M3_REV,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 4 THEN Coalesce(RA.TOTAL_REV,0) ELSE 0 END) M4_REV,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 5 THEN Coalesce(RA.TOTAL_REV,0) ELSE 0 END) M5_REV,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 6 THEN Coalesce(RA.TOTAL_REV,0) ELSE 0 END) M6_REV,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 7 THEN Coalesce(RA.TOTAL_REV,0) ELSE 0 END) M7_REV,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 8 THEN Coalesce(RA.TOTAL_REV,0) ELSE 0 END) M8_REV,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 9 THEN Coalesce(RA.TOTAL_REV,0) ELSE 0 END) M9_REV,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 10 THEN Coalesce(RA.TOTAL_REV,0) ELSE 0 END) M10_REV,
    Sum(CASE WHEN Cast(Months_Between(Trunc(REF_DATE,'MM'), Trunc(LINE_START_DATE,'MM')) AS INTEGER) = 11 THEN Coalesce(RA.TOTAL_REV,0) ELSE 0 END) M11_REV
    
FROM DP_EDW_PPF.F_LINE_SALES FLS
    INNER JOIN DP_EDW_PPF.CBU_Weeks CW ON (CW.calendar_date = FLS.ORDER_END_DT)
    INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = FLS.CUST_KEY)
    LEFT OUTER JOIN DP_EDW_PPF.F_LINE_SALES_ATTR LSA ON (LSA.SERVICE_ORDER_NUM = FLS.SERVICE_ORDER_NUM)
    LEFT OUTER JOIN DP_EDW_PPF.D_PP_PACKAGE_SRC_LKP PSL ON (PSL.SRC_SYS_CODE = LSA.OLP_PCKG)
    LEFT OUTER JOIN DP_EDW_PPF.D_PP_PACKAGE PP ON (PP.PCKG_ID = PSL.PCKG_ID)
    LEFT OUTER JOIN (SELECT QB.CUST_KEY,AWARD_LEVEL_TYPE_NAME, 
                        TB.LYLTY_LVL_STRT_DT, TB.LYLTY_LVL_END_DT
                    FROM DP_EDW_PPF.D_QITAF_BASE QB
                        INNER JOIN DP_EDW_PPF.D_TAMAYOUZ_BASE TB ON (TB.LYLTY_ACCT_ID = QB.LYLTY_ACCT_ID))T
                        ON (T.CUST_KEY = FLS.CUST_KEY AND FLS.ORDER_END_DT BETWEEN T.LYLTY_LVL_STRT_DT AND T.LYLTY_LVL_END_DT)
    LEFT OUTER JOIN DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RA ON (RA.ROOT_SUBS_KEY = FLS.ROOT_SUBS_KEY
                            AND FLS.ORDER_END_DT <= RA.REF_DATE
                            AND RA.MNTHLY_WKLY_FLAG = 'M'
                            AND RA.PERIOD_END_ACT_FLAG = 'Y')
WHERE FLS.ORDER_END_DT BETWEEN Trunc(Add_Months(DATE-2,-18),'MM') AND Trunc(DATE-2,'MM') - 1
    AND FLS.LINE_TYPE = 'PP'
    AND FLS.SALES_FLAG = 'Sales'
    --AND FLS.SCREEN_TYPE = 'SS'
GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24;







--V_PP_PCKG_IN_OUT_MTHLY

We are tracking monthly subscriber package movements.

For each ACCS_METH_KEY, we look at the package the subscriber had at one month-end and compare it with the package at the next month-end.

If the package changes:

The old package is treated as OUT (-1).
The new package is treated as IN (+1).

Example:

June: Flex 100
July: Sawa 150

Result:

Flex 100 → OUT -1
Sawa 150 → IN +1

The UNION combines the IN and OUT records.

A customer can have multiple ACCS_METH_KEYs (multiple lines), so each line is tracked separately.

The purpose is to understand how many subscribers moved from each package to another package and calculate the overall/net movement.


--SQL QUERY



SELECT MONTH_ID,
	DOMESTIC_SUBS_FLAG,
	CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
		WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P' 
	ELSE 'Others' END ID_TYPE,	
	FOCUS_GROUP,
	OTHER_GROUP,
	OTHER_GROUP_2,
	MOVEMENT,
	Count(ACCS_METH_KEY) SUBS
FROM
(SELECT T.REF_DATE MONTH_ID,
	Cast('In' AS VARCHAR(30)) AS MOVEMENT,
	T.ACCS_METH_KEY,
	T.CUST_KEY CUST_KEY_,
	T.DOMESTIC_SUBS_FLAG,
	T.HGHST_BUNDLE TO_HGHST_BUNDLE,
	F.HGHST_BUNDLE FROM_HGHST_BUNDLE,

	CASE WHEN T.HGHST_BUNDLE_TYPE = 'BTL' THEN '14. BTL' 
		WHEN T.HGHST_BUNDLE_TYPE = 'PAYG' THEN '15. PAYG' 
		WHEN T.HGHST_BUNDLE_TYPE = 'Prorated Bundle Dormant' THEN '16. Prorated Bundle Dormant' 
		WHEN T.HGHST_BUNDLE_TYPE = 'NRGS' THEN '17. NRGS' 
		ELSE
			CASE WHEN T.HGHST_BUNDLE LIKE '%FLEX%100%' THEN '10. Sawa Flex 100'
				WHEN T.HGHST_BUNDLE LIKE '%SAWA%FLEX%' THEN '11. Sawa Flex Others'
				WHEN T.HGHST_BUNDLE LIKE '%LIKE%' THEN '05. Sawa Like & Like+'
				WHEN T.HGHST_BUNDLE LIKE '%POST%' THEN '03. Sawa Post & Post+'
				WHEN T.HGHST_BUNDLE LIKE '%STAR%' THEN '02. Sawa Star & Star+'
				WHEN T.HGHST_BUNDLE LIKE '%SHARE%' THEN '04. Sawa Share & Share+'
				WHEN T.HGHST_BUNDLE LIKE '%HERO%' THEN '01. Sawa Hero'
				WHEN T.HGHST_BUNDLE LIKE '%CAPTAIN%' THEN '06. Sawa Captain'
				WHEN T.HGHST_BUNDLE LIKE '%BASIC%' THEN '07. Sawa Basic'
				WHEN T.HGHST_BUNDLE LIKE '%SAWA%150%' THEN '08. Sawa 150'
				WHEN T.HGHST_BUNDLE LIKE '%SAWA%175%' THEN '09. Sawa 175'
				WHEN T.HGHST_BUNDLE LIKE '%SAWA%120%' THEN '09. Sawa 120'
			ELSE '13. Other ATLs' END 
	END FOCUS_GROUP,	

	CASE WHEN F.ROOT_SUBS_KEY IS NOT NULL THEN 
		CASE WHEN F.HGHST_BUNDLE_TYPE = 'ATL' THEN
			CASE WHEN T.HGHST_BUNDLE_PRICE > F.HGHST_BUNDLE_PRICE THEN 'ATL-Upgraded'
				ELSE 'ATL-Downgraded/Same Price' END
			ELSE F.HGHST_BUNDLE_TYPE END
		ELSE Coalesce(SALES_FLAG,'Reconnect') END  OTHER_GROUP,
	
	CASE WHEN F.ROOT_SUBS_KEY IS NOT NULL THEN 
		CASE WHEN F.HGHST_BUNDLE_TYPE = 'ATL' THEN
			CASE WHEN F.HGHST_BUNDLE LIKE '%FLEX%100%' THEN '10. Sawa Flex 100'
				WHEN F.HGHST_BUNDLE LIKE '%SAWA%FLEX%' THEN '11. Sawa Flex Others'
				WHEN F.HGHST_BUNDLE LIKE '%LIKE%' THEN '05. Sawa Like & Like+'
				WHEN F.HGHST_BUNDLE LIKE '%POST%' THEN '03. Sawa Post & Post+'
				WHEN F.HGHST_BUNDLE LIKE '%STAR%' THEN '02. Sawa Star & Star+'
				WHEN F.HGHST_BUNDLE LIKE '%SHARE%' THEN '04. Sawa Share & Share+'
				WHEN F.HGHST_BUNDLE LIKE '%HERO%' THEN '01. Sawa Hero'
				WHEN F.HGHST_BUNDLE LIKE '%CAPTAIN%' THEN '06. Sawa Captain'
				WHEN F.HGHST_BUNDLE LIKE '%BASIC%' THEN '07. Sawa Basic'
				WHEN F.HGHST_BUNDLE LIKE '%SAWA%150%' THEN '08. Sawa 150'
				WHEN F.HGHST_BUNDLE LIKE '%SAWA%175%' THEN '09. Sawa 175'
				WHEN F.HGHST_BUNDLE LIKE '%SAWA%120%' THEN '12. Sawa 120'
			ELSE '13. Other ATLs' END 
			ELSE F.HGHST_BUNDLE_TYPE END
		ELSE Coalesce(T.ORDER_SUBTYP_NME,'Reconnect') END  OTHER_GROUP_2
	FROM
			(SELECT RA.REF_DATE,
				RA.ROOT_SUBS_KEY,
				RA.ACCS_METH_KEY,
				RA.CUST_KEY,
				RA.BUNDLE_NAME,
				RA.BUNDLE_TYPE,
				CASE WHEN RA.RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
				FLS.ORDER_SUBTYP_NME,
				CASE WHEN FLS.ORDER_SUBTYP_NME IS NOT NULL THEN 'Sales' ELSE  NULL END SALES_FLAG,
				CASE WHEN RA.RGS_30_FLAG = 'Y' THEN 'RGS' ELSE 'NRGS' END RGS_FLAG,
				CASE WHEN RGS_FLAG = 'RGS' THEN 
					CASE WHEN RA.BUNDLE_TYPE IN ('ATL','BTL','Prorated Bundle Dormant') THEN RA.BUNDLE_TYPE
					ELSE 'PAYG' END 
				ELSE RGS_FLAG END HGHST_BUNDLE_TYPE,
				CASE WHEN HGHST_BUNDLE_TYPE IN ('ATL','BTL') THEN Coalesce(PP.PCKG_GROUP_1,'90. Unknown Bundle') ELSE HGHST_BUNDLE_TYPE END HGHST_BUNDLE,
				CASE WHEN HGHST_BUNDLE_TYPE IN ('ATL','BTL') THEN Cast(PP.PRICE AS FLOAT) ELSE 0 END HGHST_BUNDLE_PRICE
			FROM DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RA
				LEFT OUTER JOIN DP_EDW_PPF.F_LINE_SALES FLS ON (FLS.ROOT_SUBS_KEY = RA.ROOT_SUBS_KEY
							AND Last_Day(FLS.ORDER_END_DT) = RA.REF_DATE)
				LEFT OUTER JOIN DP_EDW_PPF.D_PP_PACKAGE PP ON (PP.PCKG_ID = RA.BUNDLE_NAME)
			WHERE RA.REF_DATE BETWEEN Add_Months(Trunc(DATE,'MM'),-6) - 1 AND  Add_Months(Trunc(DATE,'MM'),0) - 1
				AND RA.PERIOD_END_ACT_FLAG = 'Y'
				AND RA.SCREEN_TYPE = 'SS'
				AND RA.MNTHLY_WKLY_FLAG = 'M'
				AND (RA.ACTIVE_30_FLAG = 'Y' OR RA.RGS_30_FLAG = 'Y')) T
	LEFT OUTER JOIN 
			(SELECT RA.REF_DATE,
				RA.ROOT_SUBS_KEY,
				RA.ACCS_METH_KEY,
				RA.CUST_KEY,
				RA.BUNDLE_NAME,
				RA.BUNDLE_TYPE,
				CASE WHEN RA.RGS_30_FLAG = 'Y' THEN 'RGS' ELSE 'NRGS' END RGS_FLAG,
				CASE WHEN RGS_FLAG = 'RGS' THEN 
					CASE WHEN RA.BUNDLE_TYPE IN ('ATL','BTL','Prorated Bundle Dormant') THEN RA.BUNDLE_TYPE
					ELSE 'PAYG' END 
				ELSE RGS_FLAG END HGHST_BUNDLE_TYPE,
				CASE WHEN HGHST_BUNDLE_TYPE IN ('ATL','BTL') THEN Coalesce(PP.PCKG_GROUP_1,'90. Unknown Bundle') ELSE HGHST_BUNDLE_TYPE END HGHST_BUNDLE,
				CASE WHEN HGHST_BUNDLE_TYPE IN ('ATL','BTL') THEN Cast(PP.PRICE AS FLOAT) ELSE 0 END HGHST_BUNDLE_PRICE
			FROM DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RA
				LEFT OUTER JOIN DP_EDW_PPF.D_PP_PACKAGE PP ON (PP.PCKG_ID = RA.BUNDLE_NAME)
			WHERE RA.REF_DATE BETWEEN Add_Months(Trunc(DATE,'MM'),-7) - 1 AND  Add_Months(Trunc(DATE,'MM'),-1) - 1
				AND RA.PERIOD_END_ACT_FLAG = 'Y'
				AND RA.SCREEN_TYPE = 'SS'
				AND RA.MNTHLY_WKLY_FLAG = 'M'
				AND (RA.ACTIVE_30_FLAG = 'Y' OR RA.RGS_30_FLAG = 'Y')) F
			ON (F.ACCS_METH_KEY = T.ACCS_METH_KEY AND F.REF_DATE = Trunc(T.REF_DATE, 'MM')-1))X
	INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = CUST_KEY_)
WHERE Coalesce(TO_HGHST_BUNDLE,'T') <> Coalesce(FROM_HGHST_BUNDLE,'F')
GROUP BY 1,2,3,4,5,6,7
UNION
SELECT MONTH_ID,
	DOMESTIC_SUBS_FLAG,
	CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
		WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P' 
	ELSE 'Others' END ID_TYPE,	
	FOCUS_GROUP,
	OTHER_GROUP,
	OTHER_GROUP_2,
	MOVEMENT,
	Count(ACCS_METH_KEY) * -1 SUBS
FROM
(SELECT Last_Day(F.REF_DATE + 1) MONTH_ID,
		Cast('Out' AS VARCHAR(30)) AS MOVEMENT,
		F.ACCS_METH_KEY,
		F.CUST_KEY CUST_KEY_,
		DOMESTIC_SUBS_FLAG,
		T.HGHST_BUNDLE TO_HGHST_BUNDLE,
		F.HGHST_BUNDLE FROM_HGHST_BUNDLE,

		CASE WHEN F.HGHST_BUNDLE_TYPE = 'BTL' THEN '14. BTL' 
			WHEN F.HGHST_BUNDLE_TYPE = 'PAYG' THEN '15. PAYG'
			WHEN F.HGHST_BUNDLE_TYPE = 'Prorated Bundle Dormant' THEN '16. Prorated Bundle Dormant'
			WHEN F.HGHST_BUNDLE_TYPE = 'NRGS' THEN '17. NRGS'
			ELSE
				CASE WHEN F.HGHST_BUNDLE LIKE '%FLEX%100%' THEN '10. Sawa Flex 100'
					WHEN F.HGHST_BUNDLE LIKE '%SAWA%FLEX%' THEN '11. Sawa Flex Others'
					WHEN F.HGHST_BUNDLE LIKE '%LIKE%' THEN '05. Sawa Like & Like+'
					WHEN F.HGHST_BUNDLE LIKE '%POST%' THEN '03. Sawa Post & Post+'
					WHEN F.HGHST_BUNDLE LIKE '%STAR%' THEN '02. Sawa Star & Star+'
					WHEN F.HGHST_BUNDLE LIKE '%SHARE%' THEN '04. Sawa Share & Share+'
					WHEN F.HGHST_BUNDLE LIKE '%HERO%' THEN '01. Sawa Hero'
					WHEN F.HGHST_BUNDLE LIKE '%CAPTAIN%' THEN '06. Sawa Captain'
					WHEN F.HGHST_BUNDLE LIKE '%BASIC%' THEN '07. Sawa Basic'
					WHEN F.HGHST_BUNDLE LIKE '%SAWA%150%' THEN '08. Sawa 150'
					WHEN F.HGHST_BUNDLE LIKE '%SAWA%175%' THEN '09. Sawa 175'
					WHEN F.HGHST_BUNDLE LIKE '%SAWA%120%' THEN '12. Sawa 120'
				ELSE '13. Other ATLs' END 
			END FOCUS_GROUP,	

			CASE WHEN T.ROOT_SUBS_KEY IS NOT NULL THEN 
				CASE WHEN T.HGHST_BUNDLE_TYPE = 'ATL' THEN
					CASE WHEN T.HGHST_BUNDLE_PRICE > F.HGHST_BUNDLE_PRICE THEN 'ATL-Upgraded'
						ELSE 'ATL-Downgraded/Same Price' END
					ELSE T.HGHST_BUNDLE_TYPE END
				ELSE Coalesce(CHURN_FLAG,'Dormant')END OTHER_GROUP,

			CASE WHEN T.ROOT_SUBS_KEY IS NOT NULL THEN 
				CASE WHEN T.HGHST_BUNDLE_TYPE = 'ATL' THEN
					CASE WHEN T.HGHST_BUNDLE LIKE '%FLEX%100%' THEN '10. Sawa Flex 100'
						WHEN T.HGHST_BUNDLE LIKE '%SAWA%FLEX%' THEN '11. Sawa Flex Others'
						WHEN T.HGHST_BUNDLE LIKE '%LIKE%' THEN '05. Sawa Like & Like+'
						WHEN T.HGHST_BUNDLE LIKE '%POST%' THEN '03. Sawa Post & Post+'
						WHEN T.HGHST_BUNDLE LIKE '%STAR%' THEN '02. Sawa Star & Star+'
						WHEN T.HGHST_BUNDLE LIKE '%SHARE%' THEN '04. Sawa Share & Share+'
						WHEN T.HGHST_BUNDLE LIKE '%HERO%' THEN '01. Sawa Hero'
						WHEN T.HGHST_BUNDLE LIKE '%CAPTAIN%' THEN '06. Sawa Captain'
						WHEN T.HGHST_BUNDLE LIKE '%BASIC%' THEN '07. Sawa Basic'
						WHEN T.HGHST_BUNDLE LIKE '%SAWA%150%' THEN '08. Sawa 150'
						WHEN T.HGHST_BUNDLE LIKE '%SAWA%175%' THEN '09. Sawa 175'
						WHEN T.HGHST_BUNDLE LIKE '%SAWA%120%' THEN '12. Sawa 120'
					ELSE '13. Other ATLs' END 
					ELSE T.HGHST_BUNDLE_TYPE END
				ELSE Coalesce(F.ORDER_SUBTYP_NME,'Dormant')END OTHER_GROUP_2
	FROM
			(SELECT RA.REF_DATE,
				RA.ROOT_SUBS_KEY,
				RA.ACCS_METH_KEY,
				RA.CUST_KEY,
				CASE WHEN RA.RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
				Coalesce(RA.BUNDLE_NAME,'NRGS') BUNDLE_NME,
				Coalesce(RA.BUNDLE_TYPE,'NRGS') BUNDLE_TYP,
				FLC.ORDER_SUBTYP_NME,
				CASE WHEN FLC.ORDER_SUBTYP_NME IS NOT NULL THEN 'Churn' ELSE NULL END CHURN_FLAG,
				CASE WHEN RA.RGS_30_FLAG = 'Y' THEN 'RGS' ELSE 'NRGS' END RGS_FLAG,
				CASE WHEN RGS_FLAG = 'RGS' THEN 
					CASE WHEN RA.BUNDLE_TYPE IN ('ATL','BTL','Prorated Bundle Dormant') THEN RA.BUNDLE_TYPE
					ELSE 'PAYG' END 
				ELSE RGS_FLAG END HGHST_BUNDLE_TYPE,
				CASE WHEN HGHST_BUNDLE_TYPE IN ('ATL','BTL') THEN Coalesce(PP.PCKG_GROUP_1,'90. Unknown Bundle') ELSE HGHST_BUNDLE_TYPE END HGHST_BUNDLE,
				CASE WHEN HGHST_BUNDLE_TYPE IN ('ATL','BTL') THEN Cast(PP.PRICE AS FLOAT) ELSE 0 END HGHST_BUNDLE_PRICE
			FROM DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RA
				LEFT OUTER JOIN DP_EDW_PPF.F_LINE_CHURN FLC ON (FLC.ROOT_SUBS_KEY = RA.ROOT_SUBS_KEY
								AND Last_Day(FLC.ORDER_END_DT) = Last_Day(RA.REF_DATE + 1))
				LEFT OUTER JOIN DP_EDW_PPF.D_PP_PACKAGE PP ON (PP.PCKG_ID = RA.BUNDLE_NAME)
		WHERE RA.REF_DATE BETWEEN Add_Months(Trunc(DATE,'MM'),-7) - 1 AND  Add_Months(Trunc(DATE,'MM'),-1) - 1
			AND RA.PERIOD_END_ACT_FLAG = 'Y'
			AND RA.SCREEN_TYPE = 'SS'
			AND RA.MNTHLY_WKLY_FLAG = 'M'
			AND (RA.ACTIVE_30_FLAG = 'Y' OR RA.RGS_30_FLAG = 'Y')) F
	LEFT OUTER JOIN 
			(SELECT RA.REF_DATE,
				RA.ROOT_SUBS_KEY,
				RA.ACCS_METH_KEY,
				RA.CUST_KEY,
				Coalesce(RA.BUNDLE_NAME,'NRGS') BUNDLE_NME,
				Coalesce(RA.BUNDLE_TYPE,'NRGS') BUNDLE_TYP,
				CASE WHEN RA.RGS_30_FLAG = 'Y' THEN 'RGS' ELSE 'NRGS' END RGS_FLAG,
				CASE WHEN RGS_FLAG = 'RGS' THEN 
					CASE WHEN RA.BUNDLE_TYPE IN ('ATL','BTL','Prorated Bundle Dormant') THEN RA.BUNDLE_TYPE
					ELSE 'PAYG' END 
				ELSE RGS_FLAG END HGHST_BUNDLE_TYPE,
				CASE WHEN HGHST_BUNDLE_TYPE IN ('ATL','BTL') THEN Coalesce(PP.PCKG_GROUP_1,'90. Unknown Bundle') ELSE HGHST_BUNDLE_TYPE END HGHST_BUNDLE,
				CASE WHEN HGHST_BUNDLE_TYPE IN ('ATL','BTL') THEN Cast(PP.PRICE AS FLOAT) ELSE 0 END HGHST_BUNDLE_PRICE
			FROM DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RA
				LEFT OUTER JOIN DP_EDW_PPF.D_PP_PACKAGE PP ON (PP.PCKG_ID = RA.BUNDLE_NAME)
		WHERE RA.REF_DATE BETWEEN Add_Months(Trunc(DATE,'MM'),-6) - 1 AND  Add_Months(Trunc(DATE,'MM'),0) - 1
			AND RA.PERIOD_END_ACT_FLAG = 'Y'
			AND RA.SCREEN_TYPE = 'SS'
			AND RA.MNTHLY_WKLY_FLAG = 'M'
			AND (RA.ACTIVE_30_FLAG = 'Y' OR RA.RGS_30_FLAG = 'Y')) T
		ON (F.ACCS_METH_KEY = T.ACCS_METH_KEY AND F.REF_DATE = Trunc(T.REF_DATE, 'MM')-1))X
	INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = CUST_KEY_)
WHERE Coalesce(TO_HGHST_BUNDLE,'T') <> Coalesce(FROM_HGHST_BUNDLE,'F')
GROUP BY 1,2,3,4,5,6,7;




--DP_EDW_PPF_VEW.V_PP_PCKG_MVMT_MTHLY--



This SQL creates a monthly subscriber migration view by comparing two consecutive month-end snapshots.

For each ACCS_METH_KEY, it compares:

F = previous month
T = current month

The two snapshots are matched using ACCS_METH_KEY.

The output shows:

FROM_BUNDLE_GROUP = what bundle the subscriber had in the previous month
TO_BUNDLE_GROUP = what bundle they have in the current month
FROM_CATEGORY = previous category
TO_CATEGORY = current category
OVERALL_STATUS = Existing, New Sales, Reconnects, Churned, or Dormant
FROM_REVENUE = previous month revenue
TO_REVENUE = current month revenue
REV_DIFF = change in revenue
SAME_BUNDLE_GROUP = whether the bundle group stayed the same
SAME_CATEGORY = whether the category stayed the same

The FULL OUTER JOIN is used because we need to capture:

Subscriber exists in both months → Existing / migration
Subscriber exists only in current month → New Sales or Reconnect
Subscriber exists only in previous month → Churned or Dormant

Example:

Previous month:
ACCS_METH_KEY 1001 → Flex 100

Current month:
ACCS_METH_KEY 1001 → Sawa 150

Output:

FROM_BUNDLE_GROUP = Flex 100
TO_BUNDLE_GROUP = Sawa 150
OVERALL_STATUS = Existing

The query also calculates the revenue movement:

REV_DIFF = TO_REVENUE - FROM_REVENUE

QUALIFY ROW_NUMBER() is used inside both monthly datasets to keep one record per REF_DATE + ROOT_SUBS_KEY, based on the latest sales/churn order date.

Overall, this query is used to understand where subscribers came from, where they moved to, whether they are new/churned/existing, and how their revenue changed between month-ends.


--SQL QUERY

SELECT TO_MONTH,
	FROM_MONTH,
	CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
		WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P' 
	ELSE 'Others' END ID_TYPE,
	DOMESTIC_SUBS_FLAG_,
	OVERALL_STATUS,
	FROM_BUNDLE_GROUP,
	TO_BUNDLE_GROUP,
	FROM_CATEGORY,
	TO_CATEGORY,
	CASE WHEN FROM_BUNDLE_GROUP = TO_BUNDLE_GROUP THEN 'Y' ELSE 'N' END SAME_BUNDLE_GROUP,
	CASE WHEN FROM_CATEGORY = TO_CATEGORY THEN 'Y' ELSE 'N' END SAME_CATEGORY,
	
	Count(ROOT_SUBS_KEY) SUBS,
	Sum(Coalesce(FROM_GRS_30_REV,0)) FROM_REVENUE,
	Sum(Coalesce(TO_RGS_30_REV,0)) TO_REVENUE,
	Sum(Coalesce(TO_RGS_30_REV,0) - Coalesce(FROM_GRS_30_REV,0)) REV_DIFF
FROM
(SELECT Coalesce(T.REF_DATE,Last_Day(F.REF_DATE + 1)) TO_MONTH,
	Coalesce(F.REF_DATE, Trunc(T.REF_DATE,'MM') - 1) FROM_MONTH,
	Coalesce(T.ROOT_SUBS_KEY,F.ROOT_SUBS_KEY) AS ROOT_SUBS_KEY,
	Coalesce(T.CUST_KEY,F.CUST_KEY) CUST_KEY_,
	Coalesce(T.DOMESTIC_SUBS_FLAG,F.DOMESTIC_SUBS_FLAG) DOMESTIC_SUBS_FLAG_,
	CASE WHEN T.ROOT_SUBS_KEY IS NULL AND  F.ROOT_SUBS_KEY IS NOT NULL THEN 
			CASE WHEN CHURN_TYPE IS NOT NULL THEN 'Churned' ELSE 'Dormant' END
		WHEN T.ROOT_SUBS_KEY IS NOT NULL AND F.ROOT_SUBS_KEY IS NULL THEN
			CASE WHEN SALES_TYPE IS NOT NULL THEN 'New Sales' ELSE 'Reconnects' END
		ELSE 'Existing' END OVERALL_STATUS,
			
	
	SALES_TYPE,
	CHURN_TYPE,
	CASE WHEN F.BUNDLE_GROUP IS NULL THEN Coalesce(SALES_TYPE,'Reconnects') ELSE F.BUNDLE_GROUP END FROM_BUNDLE_GROUP,
	CASE WHEN T.BUNDLE_GROUP IS NULL THEN Coalesce(CHURN_TYPE,'Dormant') ELSE T.BUNDLE_GROUP END TO_BUNDLE_GROUP,
	CASE WHEN F.CATEGORY IS NULL THEN Coalesce(SALES_TYPE,'Reconnects') ELSE F.CATEGORY END FROM_CATEGORY,
	CASE WHEN T.CATEGORY IS NULL THEN Coalesce(CHURN_TYPE,'Dormant') ELSE T.CATEGORY END TO_CATEGORY,
	
	Coalesce(T.PRICE,0) TO_PRICE,
	Coalesce(F.PRICE,0) FROM_PRICE,
	
	T.RGS_30D_REV TO_RGS_30_REV,
	F.RGS_30D_REV FROM_GRS_30_REV,
	T.SUBS_REV TO_SUBS_REV,
	F.SUBS_REV FROM_SUBS_REV
FROM
		(SELECT RA.REF_DATE,
			RA.ROOT_SUBS_KEY,
			RA.ACCS_METH_KEY,
			RA.CUST_KEY,
			CASE WHEN RA.RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
			'New Sales - ' || FLS.ORDER_SUBTYP_NME   SALES_TYPE,
			CASE WHEN RA.RGS_30_FLAG = 'Y' THEN 'RGS' ELSE 'NRGS' END RGS_FLAG,
			CASE WHEN RA.RGS_30_FLAG = 'Y' THEN RA.BUNDLE_TYPE ELSE 'NRGS' END BUNDLE_TYPE_,
			CASE WHEN RA.RGS_30_FLAG = 'Y' THEN RA.BUNDLE_NAME ELSE 'NRGS' END BUNDLE_NAME_,
			CASE WHEN RGS_FLAG = 'RGS' THEN 
				CASE WHEN RA.BUNDLE_TYPE IN ('ATL','BTL') THEN Coalesce(PP.PCKG_GROUP_1,'90. Unknown Bundle') 
					WHEN RA.BUNDLE_TYPE = 'Prorated Bundle Dormant' THEN '98. Prorated Bundle Dormant'
				ELSE '97. PAYG' END
			ELSE '99. NRGS' END BUNDLE_GROUP,
			CASE WHEN RGS_FLAG = 'RGS' THEN
				CASE WHEN RA.BUNDLE_TYPE = 'BTL' THEN '14. BTL' 
					WHEN RA.BUNDLE_TYPE = 'Prorated Bundle Dormant' THEN '16. Prorated Bundle Dormant'
					WHEN RA.BUNDLE_TYPE = 'ATL' THEN
						CASE WHEN PP.PCKG_GROUP_1 LIKE '%FLEX%100%' THEN '10. Sawa Flex 100'
							WHEN PP.PCKG_GROUP_1 LIKE '%SAWA%FLEX%' THEN '11. Sawa Flex Others'
							WHEN PP.PCKG_GROUP_1 LIKE '%LIKE%' THEN '05. Sawa Like & Like+'
							WHEN PP.PCKG_GROUP_1 LIKE '%POST%' THEN '03. Sawa Post & Post+'
							WHEN PP.PCKG_GROUP_1 LIKE '%STAR%' THEN '02. Sawa Star & Star+'
							WHEN PP.PCKG_GROUP_1 LIKE '%SHARE%' THEN '04. Sawa Share & Share+'
							WHEN PP.PCKG_GROUP_1 LIKE '%HERO%' THEN '01. Sawa Hero'
							WHEN PP.PCKG_GROUP_1 LIKE '%CAPTAIN%' THEN '06. Sawa Captain'
							WHEN PP.PCKG_GROUP_1 LIKE '%BASIC%' THEN '07. Sawa Basic'
							WHEN PP.PCKG_GROUP_1 LIKE '%SAWA%150%' THEN '08. Sawa 150'
							WHEN PP.PCKG_GROUP_1 LIKE '%SAWA%175%' THEN '09. Sawa 175'
							WHEN PP.PCKG_GROUP_1 LIKE '%SAWA%120%' THEN '12. Sawa 120'
						ELSE '13. Other ATLs' END
				ELSE '15. PAYG' END 
			ELSE '17. NRGS' END CATEGORY,
			CASE WHEN RA.RGS_30_FLAG = 'Y' THEN CASE WHEN RA.BUNDLE_TYPE IN ('ATL','BTL') THEN PP.PRICE_RANGE ELSE 'PAYG' END ELSE 'NRGS' END PRICE_RANGE_,
			PP.PRICE,
			RA.RGS_30D_REV,
			RA.TOTAL_REV,
			(Coalesce(RA.ATL_REV,0) + Coalesce(RA.BTL_REV,0)) SUBS_REV
		FROM DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RA
			LEFT OUTER JOIN DP_EDW_PPF.F_LINE_SALES FLS ON (FLS.ROOT_SUBS_KEY = RA.ROOT_SUBS_KEY
					AND Last_Day(FLS.ORDER_END_DT) = RA.REF_DATE)
			LEFT OUTER JOIN DP_EDW_PPF.D_PP_PACKAGE PP ON (PP.PCKG_ID = RA.BUNDLE_NAME)
		WHERE RA.REF_DATE BETWEEN Add_Months(Trunc(DATE,'MM'),-6) - 1 AND  Add_Months(Trunc(DATE,'MM'),0) - 1
			AND RA.PERIOD_END_ACT_FLAG = 'Y'
			AND RA.SCREEN_TYPE = 'SS'
			AND RA.MNTHLY_WKLY_FLAG = 'M'
			AND (RA.ACTIVE_30_FLAG = 'Y' OR RA.RGS_30_FLAG = 'Y')
		QUALIFY Row_Number() Over(PARTITION BY RA.REF_DATE, RA.ROOT_SUBS_KEY ORDER BY FLS.ORDER_END_DT DESC) = 1) T
FULL OUTER JOIN 
		(SELECT RA.REF_DATE,
			RA.ROOT_SUBS_KEY,
			RA.ACCS_METH_KEY,
			RA.CUST_KEY,
			CASE WHEN RA.RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
			'Churn - ' || FLC.ORDER_SUBTYP_NME  CHURN_TYPE,
			CASE WHEN RA.RGS_30_FLAG = 'Y' THEN 'RGS' ELSE 'NRGS' END RGS_FLAG,
			CASE WHEN RA.RGS_30_FLAG = 'Y' THEN RA.BUNDLE_TYPE ELSE 'NRGS' END BUNDLE_TYPE_,
			CASE WHEN RA.RGS_30_FLAG = 'Y' THEN RA.BUNDLE_NAME ELSE 'NRGS' END BUNDLE_NAME_,
			CASE WHEN RGS_FLAG = 'RGS' THEN 
				CASE WHEN RA.BUNDLE_TYPE IN ('ATL','BTL') THEN Coalesce(PP.PCKG_GROUP_1,'90. Unknown Bundle') 
					WHEN RA.BUNDLE_TYPE = 'Prorated Bundle Dormant' THEN '98. Prorated Bundle Dormant'
				ELSE '97. PAYG' END
			ELSE '99. NRGS' END BUNDLE_GROUP,
			CASE WHEN RGS_FLAG = 'RGS' THEN
				CASE WHEN RA.BUNDLE_TYPE = 'BTL' THEN '14. BTL' 
					WHEN RA.BUNDLE_TYPE = 'Prorated Bundle Dormant' THEN '16. Prorated Bundle Dormant'
					WHEN RA.BUNDLE_TYPE = 'ATL' THEN
						CASE WHEN PP.PCKG_GROUP_1 LIKE '%FLEX%100%' THEN '10. Sawa Flex 100'
							WHEN PP.PCKG_GROUP_1 LIKE '%SAWA%FLEX%' THEN '11. Sawa Flex Others'
							WHEN PP.PCKG_GROUP_1 LIKE '%LIKE%' THEN '05. Sawa Like & Like+'
							WHEN PP.PCKG_GROUP_1 LIKE '%POST%' THEN '03. Sawa Post & Post+'
							WHEN PP.PCKG_GROUP_1 LIKE '%STAR%' THEN '02. Sawa Star & Star+'
							WHEN PP.PCKG_GROUP_1 LIKE '%SHARE%' THEN '04. Sawa Share & Share+'
							WHEN PP.PCKG_GROUP_1 LIKE '%HERO%' THEN '01. Sawa Hero'
							WHEN PP.PCKG_GROUP_1 LIKE '%CAPTAIN%' THEN '06. Sawa Captain'
							WHEN PP.PCKG_GROUP_1 LIKE '%BASIC%' THEN '07. Sawa Basic'
							WHEN PP.PCKG_GROUP_1 LIKE '%SAWA%150%' THEN '08. Sawa 150'
							WHEN PP.PCKG_GROUP_1 LIKE '%SAWA%175%' THEN '09. Sawa 175'
							WHEN PP.PCKG_GROUP_1 LIKE '%SAWA%120%' THEN '12. Sawa 120'
						ELSE '13. Other ATLs' END
				ELSE '15. PAYG' END 
			ELSE '17. NRGS' END CATEGORY,
			CASE WHEN RA.RGS_30_FLAG = 'Y' THEN CASE WHEN RA.BUNDLE_TYPE IN ('ATL','BTL') THEN PP.PRICE_RANGE ELSE 'PAYG' END ELSE 'NRGS' END PRICE_RANGE_,
			PP.PRICE,
			RA.RGS_30D_REV,
			RA.TOTAL_REV,
			(Coalesce(RA.ATL_REV,0) + Coalesce(RA.BTL_REV,0)) SUBS_REV
		FROM DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RA
			LEFT OUTER JOIN DP_EDW_PPF.F_LINE_CHURN FLC ON (FLC.ROOT_SUBS_KEY = RA.ROOT_SUBS_KEY
					AND Last_Day(FLC.ORDER_END_DT) = Last_Day(RA.REF_DATE+1))
			LEFT OUTER JOIN DP_EDW_PPF.D_PP_PACKAGE PP ON (PP.PCKG_ID = RA.BUNDLE_NAME)
		WHERE RA.REF_DATE BETWEEN Add_Months(Trunc(DATE,'MM'),-7) - 1 AND  Add_Months(Trunc(DATE,'MM'),-1) - 1
			AND RA.PERIOD_END_ACT_FLAG = 'Y'
			AND RA.SCREEN_TYPE = 'SS'
			AND RA.MNTHLY_WKLY_FLAG = 'M'
			AND (RA.ACTIVE_30_FLAG = 'Y' OR RA.RGS_30_FLAG = 'Y')
		QUALIFY Row_Number() Over(PARTITION BY RA.REF_DATE, RA.ROOT_SUBS_KEY ORDER BY FLC.ORDER_END_DT DESC) = 1) F
	ON (F.ACCS_METH_KEY = T.ACCS_METH_KEY AND F.REF_DATE = Trunc(T.REF_DATE, 'MM')-1))X
				INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = CUST_KEY_)
GROUP BY 1,2,3,4,5,6,7,8,9,10,11;


	
--DP_EDW_PPF_VEW.V_PP_BUNDLE_WRKG_LNS_BY_PCKG

--CONTEXT
the Below query is used to get the bundle working lines by package
for the main subscriptions/ working lines and rateplan we are using DP_EDW_PPF.F_PP_PACKAGE_SUBSCRIPTIONS 
for id type and cust details we are using DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST cust_key column to join.
for the product details or package details we use DP_EDW_PPF.D_PP_PACKAGE  table by joining to pckg_id.
for calender days , weeks etc we are using this table DP_EDW_PPF.CBU_Weeks 


-- sql query--

SELECT CW.calendar_date REF_DATE,
	CASE WHEN CW.calendar_date = CW.LST_DAY_OF_MTH THEN 'Monthly' ELSE 'Weekly' END MONTHLY_WEEKLY,
    CW.CBU_MONTH_ID,
    CW.CBU_WEEK_ID,
    CW.CBU_MONTH_NUM,
    CW.CBU_WEEK_NUM,
	CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
        WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P' 
        ELSE 'Others' END ID_TYPE,
	CASE WHEN ID_TYPE = 'S' THEN 'Saudi' ELSE
        CASE WHEN CL.CUST_NAT_CD IN ('Yemen','Bangladesh','India','Pakistan','Sudan',
            'Egypt','Philippines','Syria','Ethiopia','Indonesia','Nepal') THEN CL.CUST_NAT_CD ELSE 'Other' END END NATIONALITY,
	PPS.SCREEN_TYPE,
	CASE WHEN PPS.RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
	CASE WHEN PPS.SCREEN_TYPE  = 'SS' THEN 
		CASE WHEN PPS.RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah'
			WHEN PPS.RATEPLAN = 'SAWA Postpaid' THEN 'SAWA Postpaid'
			WHEN PPS.RATEPLAN = 'Prepaid Voice SAWA Workers' THEN 'SAWA Workers'
			ELSE 'SAWA Regular' END
		ELSE PPS.RATEPLAN END AS RATEPLAN,
	PP.PCKG_TYPE OFFER_TYPE,
	CASE WHEN PP.PCKG_TYPE = 'ATL' THEN
		CASE WHEN PP.PCKG_NAME LIKE '%FLEX%100%' THEN '10. Sawa Flex 100'
			WHEN PP.PCKG_NAME LIKE '%SAWA%FLEX%' THEN '11. Sawa Flex Others'
			WHEN PP.PCKG_NAME LIKE '%LIKE%' THEN '05. Sawa Like & Like+'
			WHEN PP.PCKG_NAME LIKE '%POST%' THEN '03. Sawa Post & Post+'
			WHEN PP.PCKG_NAME LIKE '%STAR%' THEN '02. Sawa Star & Star+'
			WHEN PP.PCKG_NAME LIKE '%SHARE%' THEN '04. Sawa Share & Share+'
			WHEN PP.PCKG_NAME LIKE '%HERO%' THEN '01. Sawa Hero'
			WHEN PP.PCKG_NAME LIKE '%CAPTAIN%' THEN '06. Sawa Captain'
			WHEN PP.PCKG_NAME LIKE '%BASIC%' THEN '07. Sawa Basic'
			WHEN PP.PCKG_NAME LIKE '%SAWA%150%' THEN '08. Sawa 150'
			WHEN PP.PCKG_NAME LIKE '%SAWA%175%' THEN '09. Sawa 175'
		ELSE '12. Other ATLs' END ELSE PP.PCKG_TYPE END AS GROUP_1,
	PP.PCKG_GROUP_1 GROUP_2,
	PP.PRICE_RANGE,
	PP.PCKG_SUB_CATEGORY,
	PP.PCKG_CATEGORY,
	PPS.CHANNEL,
	Sum(PPS.SUBSCRIPTION_CNT) SUBS
FROM DP_EDW_PPF.CBU_Weeks CW
	INNER JOIN DP_EDW_PPF.F_PP_PACKAGE_SUBSCRIPTIONS PPS ON (CW.calendar_date BETWEEN PPS.SUBSCRIPTION_START_DT AND PPS.SUBSCRIPTION_END_DT)
	INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = PPS.CUST_KEY)
	INNER JOIN DP_EDW_PPF.D_PP_PACKAGE PP ON (PP.PCKG_ID = PPS.PCKG_ID)
WHERE CW.calendar_date BETWEEN Add_Months(Trunc(DATE,'MM'),-24) AND Trunc(DATE,'MM') - 1 
	AND PPS.SUBSCRIPTION_START_DT >= DATE '2025-01-01'
	AND (CW.calendar_date = CW.LST_DAY_OF_MTH)
	AND PP.PCKG_SERVICE_TYPE = 'SAWA'
	AND PP.PCKG_TYPE IN ('ATL','BTL')
	AND PPS.SCREEN_TYPE = 'SS'
GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18;




-- DP_EDW_PPF_VEW.V_PP_BUNDLE_WRKG_LNS_BY_PCKG_dly

THIS QUERY IS SAME AS THE BUNDLE WORKING LINES BUT ONLY DIFFERENCE IS THAT THIS IS DAILY

SELECT CW.calendar_date REF_DATE,
    CW.LST_DAY_OF_MTH,
	CW.LST_DAY_OF_WK,
	CW.CBU_MONTH_ID,
    CW.CBU_WEEK_ID,
    CW.CBU_MONTH_NUM,
	CW.CBU_WEEK_NUM,
    CW.day_of_month,
	CW.Day_Of_WEEK,
	CASE WHEN CW.day_of_month <= Extract(DAY From DATE - 1) THEN 'Y' ELSE 'N' END MTD_FLAG, 
	CASE WHEN CW.day_of_month = Extract(DAY From DATE - 1) THEN 'Y' ELSE 'N' END FIXED_MTD_FLAG, -- Fixed one Day 
	CASE WHEN CW.LST_Day_Of_MTH = CW.calendar_date THEN CW.calendar_date
 			WHEN CW.calendar_date = (SELECT Max(REF_DATE) FROM DP_EDW_PPF.F_PP_DAILY_ACTIVE_30 
									WHERE REF_DATE BETWEEN DATE - 5 AND DATE) THEN CW.calendar_date ELSE NULL END Month_End_DT,
	CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
        WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P' 
        ELSE 'Others' END ID_TYPE,
	CASE WHEN ID_TYPE = 'S' THEN 'Saudi' ELSE
        CASE WHEN CL.CUST_NAT_CD IN ('Yemen','Bangladesh','India','Pakistan','Sudan',
            'Egypt','Philippines','Syria','Ethiopia','Indonesia','Nepal') THEN CL.CUST_NAT_CD ELSE 'Other' END END NATIONALITY,
	CASE WHEN PPS.RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
	PP.PCKG_TYPE OFFER_TYPE,
	CASE WHEN PP.PCKG_TYPE = 'ATL' THEN
		CASE WHEN PP.PCKG_NAME LIKE '%FLEX%100%' THEN '10. Sawa Flex 100'
			WHEN PP.PCKG_NAME LIKE '%SAWA%FLEX%' THEN '11. Sawa Flex Others'
			WHEN PP.PCKG_NAME LIKE '%LIKE%' THEN '05. Sawa Like & Like+'
			WHEN PP.PCKG_NAME LIKE '%POST%' THEN '03. Sawa Post & Post+'
			WHEN PP.PCKG_NAME LIKE '%STAR%' THEN '02. Sawa Star & Star+'
			WHEN PP.PCKG_NAME LIKE '%SHARE%' THEN '04. Sawa Share & Share+'
			WHEN PP.PCKG_NAME LIKE '%HERO%' THEN '01. Sawa Hero'
			WHEN PP.PCKG_NAME LIKE '%CAPTAIN%' THEN '06. Sawa Captain'
			WHEN PP.PCKG_NAME LIKE '%BASIC%' THEN '07. Sawa Basic'
			WHEN PP.PCKG_NAME LIKE '%SAWA%150%' THEN '08. Sawa 150'
			WHEN PP.PCKG_NAME LIKE '%SAWA%175%' THEN '09. Sawa 175'
			WHEN PP.PCKG_NAME LIKE '%SAWA%120%' THEN '12. Sawa 120'
		ELSE '13. Other ATLs' END ELSE PP.PCKG_TYPE END AS GROUP_1,
	PP.PCKG_GROUP_1 GROUP_2,
	PP.PRICE_RANGE,
	PP.PCKG_SUB_CATEGORY,
	PPS.CHANNEL,
	Sum(PPS.SUBSCRIPTION_CNT) SUBS
FROM DP_EDW_PPF.CBU_Weeks CW
	INNER JOIN DP_EDW_PPF.F_PP_PACKAGE_SUBSCRIPTIONS PPS ON (CW.calendar_date BETWEEN PPS.SUBSCRIPTION_START_DT AND PPS.SUBSCRIPTION_END_DT)
	INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = PPS.CUST_KEY)
	INNER JOIN DP_EDW_PPF.D_PP_PACKAGE PP ON (PP.PCKG_ID = PPS.PCKG_ID)
WHERE CW.calendar_date BETWEEN Add_Months(Trunc(DATE - 3 ,'MM'),-3)  AND DATE - 1 
	AND PP.PCKG_SERVICE_TYPE = 'SAWA'
	AND PP.PCKG_TYPE IN ('ATL','BTL')
	AND PPS.SCREEN_TYPE = 'SS'
GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21;


--DP_EDW_PPF_VEW.V_PP_PCKG_ACT_REV_DLY

--CONTEXT 
This query is for daily SAWA SUBSCRIPTIONS REVENUE and Sawa ACTIVATIONS.


Looks at SAWA subscriptions.
Gets customer, package, SIM, channel, and rate-plan details.
Covers the last 3 months and a historical period from last year.
Groups the data by day and business categories.
Calculates Revenue and Activations.

Main output: Daily SAWA Revenue and Activations broken down by different customer and package attributes.

Important: It is a daily query, not a monthly query.


--SQL QUERY--

DP_EDW_PPF_VEW.V_PP_PCKG_ACT_REV_DLY

SELECT PPS.SUBSCRIPTION_START_DT, 
    CW.LST_DAY_OF_MTH, 
    CW.CBU_MONTH_ID,
    CW.CBU_WEEK_ID,
    CW.CBU_MONTH_NUM,
    CW.day_of_month,
    CASE WHEN CW.day_of_month <= Extract(DAY From DATE - 1) THEN 'Y' ELSE 'N' END MTD_FLAG,
    CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
        WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P' 
        ELSE 'Others' END ID_TYPE,
    CASE WHEN ID_TYPE = 'S' THEN 'Saudi' ELSE
        CASE WHEN CL.CUST_NAT_CD IN ('Yemen','Bangladesh','India','Pakistan','Sudan',
            'Egypt','Philippines','Syria','Ethiopia','Indonesia','Nepal') THEN CL.CUST_NAT_CD ELSE 'Other' END END NATIONALITY,
    PP.PCKG_TYPE,
    CASE WHEN PP.PCKG_SUB_CATEGORY IN ('Monthly','Daily','Weekly') THEN PP.PCKG_SUB_CATEGORY ELSE 'Others' END VALIDTY, 
    PP.PCKG_GROUP_1,
    PP.PRICE_RANGE,
	CASE WHEN PP.PCKG_TYPE = 'ATL' THEN
		CASE WHEN PP.PCKG_NAME LIKE '%FLEX%100%' THEN '10. Sawa Flex 100'
			WHEN PP.PCKG_NAME LIKE '%FLEX%' THEN '11. Sawa Flex Others'
			WHEN PP.PCKG_NAME LIKE '%LIKE%' THEN '05. Sawa Like & Like+'
			WHEN PP.PCKG_NAME LIKE '%POST%' THEN '03. Sawa Post & Post+'
			WHEN PP.PCKG_NAME LIKE '%STAR%' THEN '02. Sawa Star & Star+'
			WHEN PP.PCKG_NAME LIKE '%SHARE%' THEN '04. Sawa Share & Share+'
			WHEN PP.PCKG_NAME LIKE '%HERO%' THEN '01. Sawa Hero'
			WHEN PP.PCKG_NAME LIKE '%CAPTAIN%' THEN '06. Sawa Captain'
			WHEN PP.PCKG_NAME LIKE '%BASIC%' THEN '07. Sawa Basic'
			WHEN PP.PCKG_NAME LIKE '%SAWA%150%' THEN '08. Sawa 150'
			WHEN PP.PCKG_NAME LIKE '%SAWA%175%' THEN '09. Sawa 175'
		ELSE '12. Other ATLs' END ELSE PP.PCKG_TYPE END AS GROUP_2,
	PPS.CHANNEL,
	CASE WHEN PSL.SIM_TYPE = 'E-SIM' THEN PSL.SIM_TYPE ELSE 'Physical SIM' END SIM_TYP,
	CASE WHEN PPS.RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
    CASE WHEN PPS.SCREEN_TYPE  = 'SS' THEN 
		CASE WHEN PPS.RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah'
			WHEN PPS.RATEPLAN = 'SAWA Postpaid' THEN 'SAWA Postpaid'
			WHEN PPS.RATEPLAN = 'Prepaid Voice SAWA Workers' THEN 'SAWA Workers'
			ELSE 'SAWA Regular' END
		ELSE PPS.RATEPLAN END AS RATE_PLAN,
    Sum(PPS.SUBSCRIPTION_REVENUE) REVENUE,
    Sum(PPS.SUBSCRIPTION_CNT) ACTIVATIONS
FROM DP_EDW_PPF.F_PP_PACKAGE_SUBSCRIPTIONS PPS
	INNER JOIN DP_EDW_PPF.D_PP_PACKAGE PP ON (PP.PCKG_ID = PPS.PCKG_ID)
	INNER JOIN DP_EDW_PPF.D_PP_PACKAGE_SRC_LKP PSL ON (PSL.SRC_SYS_CODE = PPS.PACKAGEX
				AND PSL.DATA_SOURCE_SYSTEM = PPS.DATA_SOURCE
				AND PPS.SUBSCRIPTION_START_DT BETWEEN PSL.REC_START_DT AND PSL.REC_END_DT)
    INNER JOIN DP_EDW_PPF.CBU_Weeks CW ON (CW.calendar_date = PPS.SUBSCRIPTION_START_DT)
    INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = PPS.CUST_KEY)
WHERE PP.PCKG_SERVICE_TYPE = 'SAWA'
	AND PPS.SCREEN_TYPE = 'SS'
	AND (CW.calendar_date BETWEEN Add_Months(Trunc(DATE - 2,'MM'),-3) AND DATE - 1
		OR CW.calendar_date BETWEEN Add_Months(Trunc(DATE - 2,'MM'),-12) AND Add_Months(Trunc(DATE - 2,'MM'),-11) - 1)
GROUP BY 1,2,3,4,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18;


--DP_EDW_PPF_VEW.V_PP_PCKG_ACT_REV_MTHLY_WKLY

CONTEXT
This is basically the same query as the one above, with some minor changes.

The main purpose is still to analyze SAWA subscriptions, including Revenue and Activations, using customer, package, nationality, channel, subscriber type, and rate-plan information.

The main difference is that this version is monthly instead of daily AND ALSO WE CAN GET WEEKLY . It groups the data by month rather than by subscription date.

It also:

Covers January 2025 up to the last completed month.
Uses YTM_FLAG instead of the previous MTD_FLAG.
Has updated package groupings (GROUP_2).
Keeps the same main Revenue and Activations calculations.
Uses the same main source tables and joins.

In simple terms:
This is the monthlY AND WEEKLY version of the previous SAWA query, with updated date logic, package grouping, and the YTM_FLAG.

--SQL QUERY

SELECT 
    CW.year_of_calendar,
    CW.CBU_MONTH_ID,
    CW.LST_DAY_OF_MTH,
    CW.CBU_MONTH_NUM,

    CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
         WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P'
         ELSE 'Others' END AS ID_TYPE,

    CASE WHEN ID_TYPE = 'S' THEN 'Saudi' 
         ELSE CASE WHEN CL.CUST_NAT_CD IN ('Yemen','Bangladesh','India','Pakistan','Sudan',
                   'Egypt','Philippines','Syria','Ethiopia','Indonesia','Nepal') 
                   THEN CL.CUST_NAT_CD ELSE 'Other' END 
    END AS NATIONALITY,

    PP.PCKG_TYPE,

    CASE WHEN PP.PCKG_SUB_CATEGORY IN ('Monthly','Daily','Weekly') 
         THEN PP.PCKG_SUB_CATEGORY ELSE 'Others' END AS VALIDTY,

    PP.PCKG_GROUP_1,
    PP.PRICE_RANGE,

    CASE WHEN PP.PCKG_TYPE = 'ATL' THEN
            CASE WHEN PP.PCKG_NAME LIKE ANY ('%HERO%','%FLEX%340%')     THEN '01. Hero/Flex 340'
			 	WHEN PP.PCKG_NAME LIKE ANY ('%STAR%','%FLEX%240%')     THEN '02. Star/Flex 240'
			 	WHEN PP.PCKG_NAME LIKE '%SAWA%175%' THEN '03. Sawa 175'
			 	WHEN PP.PCKG_NAME LIKE '%POST%'     THEN '04. Post & Post+'
				WHEN PP.PCKG_NAME LIKE ANY ('%SAWA%150%','%FLEX%150%')  THEN '05. Sawa/Flex 150'
				WHEN PP.PCKG_NAME LIKE '%SAWA%120%' THEN '06. Sawa 120'
			 	WHEN PP.PCKG_NAME LIKE '%SHARE%'    THEN '07. Share & Share+'
			 	WHEN PP.PCKG_NAME LIKE '%FLEX%100%' THEN '08. Flex 100'
				WHEN PP.PCKG_NAME LIKE '%CAPTAIN%'  THEN '09. Captain'
				WHEN PP.PCKG_NAME LIKE ANY ('%LIKE%','%FLEX%65%')   THEN '10. Like/Flex 65'
				WHEN PP.PCKG_NAME LIKE ANY ('%BASIC%','%FLEX%35%')    THEN '11. Basic/Flex 35'
            ELSE '12. Other ATLs/Ziyarah' END
         ELSE PP.PCKG_TYPE 
    END AS GROUP_2,

    PPS.CHANNEL,

    CASE WHEN PPS.RATEPLAN LIKE '%Ziyara%' 
         THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' 
    END AS DOMESTIC_SUBS_FLAG,

    CASE WHEN PPS.SCREEN_TYPE = 'SS' THEN
             CASE WHEN PPS.RATEPLAN LIKE '%Ziyara%'              THEN 'Ziyarah'
                  WHEN PPS.RATEPLAN = 'SAWA Postpaid'            THEN 'SAWA Postpaid'
                  WHEN PPS.RATEPLAN = 'Prepaid Voice SAWA Workers' THEN 'SAWA Workers'
                  ELSE 'SAWA Regular' END
         ELSE PPS.RATEPLAN 
    END AS RATE_PLAN,

CASE WHEN Extract(MONTH From calendar_date) <= Extract(MONTH From (Trunc(DATE - 2,'MM') - 1))
                THEN 'Y' ELSE 'N' END AS YTM_FLAG,

    Sum(PPS.SUBSCRIPTION_REVENUE) AS REVENUE,
    Sum(PPS.SUBSCRIPTION_CNT)     AS ACTIVATIONS

FROM DP_EDW_PPF.F_PP_PACKAGE_SUBSCRIPTIONS PPS
    INNER JOIN DP_EDW_PPF.D_PP_PACKAGE PP 
        ON (PP.PCKG_ID = PPS.PCKG_ID)
    INNER JOIN DP_EDW_PPF.D_PP_PACKAGE_SRC_LKP PSL 
        ON (PSL.SRC_SYS_CODE        = PPS.PACKAGEX
        AND PSL.DATA_SOURCE_SYSTEM  = PPS.DATA_SOURCE
        AND PPS.SUBSCRIPTION_START_DT BETWEEN PSL.REC_START_DT AND PSL.REC_END_DT)
    INNER JOIN DP_EDW_PPF.CBU_Weeks CW 
        ON (CW.calendar_date = PPS.SUBSCRIPTION_START_DT)
    INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL 
        ON (CL.CUST_KEY = PPS.CUST_KEY)

WHERE PP.PCKG_SERVICE_TYPE = 'SAWA'
  AND CW.calendar_date BETWEEN Add_Months(Trunc(DATE - 2,'MM'), -24) AND DATE - 1
  AND CW.calendar_date BETWEEN DATE '2025-01-01' AND Trunc(DATE - 2,'MM') - 1

GROUP BY 
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15;
	


--DP_EDW_PPF_VEW.V_PP_PCKG_RENEWAL_DLY

--CONTEXT 

This query analyzes SAWA Monthly package expiries and renewals.

It looks at customers whose monthly SAWA packages are expiring around the current period, and checks whether they renewed or did not renew.

It also identifies:

Whether the package has expired.
Whether the customer renewed.
Whether they renewed with the same or different package.
What package type they renewed with.
Whether the renewed package is Monthly, Weekly, Daily, etc.
The renewal timing compared with the expiry date:
On or before expiry
Within 1 week after expiry
More than 1 week after expiry


SELECT CW.LST_DAY_OF_MTH, 
    CW.CBU_MONTH_ID,
    CW.CBU_WEEK_ID,
    CW.CBU_MONTH_NUM,
    CW.DAY_OF_MONTH,
    CASE WHEN CW.day_of_month <= Extract(DAY From DATE - 1) THEN 'Y' ELSE 'N' END MTD_FLAG,
    CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
        WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P' 
        ELSE 'Others' END ID_TYPE,
    CASE WHEN ID_TYPE = 'S' THEN 'Saudi' ELSE
		CASE WHEN CL.CUST_NAT_CD IN ('Yemen','Bangladesh','India','Pakistan','Sudan',
    			'Egypt','Philippines','Syria','Ethiopia','Indonesia','Nepal') THEN CL.CUST_NAT_CD ELSE 'Other' END END NATIONALITY,
	CURR_PCKG_TYPE,	
	CURR_PRICE_RANGE,
	EXPIRED_FLAG,
	RENEWED_FLAG,
	RENEWED_PCKG_TYPE,			
	RENEWED_VALIDTY,
	RENEWAL_WINDOW,
	SAME_PCKG_FLAG,
	Count(X.ROOT_SUBS_KEY) SUBS
FROM
	(SELECT PPS.SUBSCRIPTION_END_DT EXPIRY_DATE,
		PPS.CUST_KEY,
		PP.PCKG_TYPE CURR_PCKG_TYPE,
		CASE WHEN PP.PCKG_SUB_CATEGORY IN ('Monthly','Daily','Weekly') THEN PP.PCKG_SUB_CATEGORY ELSE 'Others' END CURR_VALIDTY, 
		PP.PRICE_RANGE CURR_PRICE_RANGE,
		CASE WHEN PPSR.ROOT_SUBS_KEY IS NOT NULL THEN 'Renewed' ELSE 'Not Renewed' END RENEWED_FLAG,
		CASE WHEN PPSR.ROOT_SUBS_KEY IS NULL THEN 'No Renewed' ELSE
				CASE WHEN PP.PCKG_ID = PPR.PCKG_ID THEN 'Same Pckg' ELSE 'Diff Pckg' END END SAME_PCKG_FLAG,
		Coalesce(PPR.PCKG_TYPE,'Not Renewed') RENEWED_PCKG_TYPE,
		CASE WHEN PPSR.ROOT_SUBS_KEY IS NULL THEN 'Not Renewed' ELSE 
				CASE WHEN PP.PCKG_SUB_CATEGORY IN ('Monthly','Daily','Weekly') THEN PP.PCKG_SUB_CATEGORY ELSE 'Others' END END RENEWED_VALIDTY,
		CASE WHEN PPSR.ROOT_SUBS_KEY IS NULL THEN 'Not Renewed' ELSE PPR.PRICE_RANGE END RENEWED_PRICE_RANGE,
		PPS.PCKG_ID,
		PPS.ROOT_SUBS_KEY,
		PPSR.SUBSCRIPTION_START_DT RENEWAL_DATE,
		CASE WHEN EXPIRY_DATE <= DATE - 1 THEN 'Expired' ELSE 'Not Yet Expired' END EXPIRED_FLAG,
		CASE WHEN EXPIRY_DATE IS NULL THEN 'Not Renewed' ELSE
			CASE WHEN RENEWAL_DATE <= EXPIRY_DATE THEN 'On or Before Expiry'
			WHEN RENEWAL_DATE BETWEEN EXPIRY_DATE AND EXPIRY_DATE + 7 THEN 'Within 1 WK of Expiry' 
			ELSE 'After 1 WK of Expiry' END END RENEWAL_WINDOW
	FROM DP_EDW_PPF.F_PP_PACKAGE_SUBSCRIPTIONS PPS
		INNER JOIN DP_EDW_PPF.D_PP_PACKAGE PP ON (PP.PCKG_ID = PPS.PCKG_ID)
		LEFT OUTER JOIN DP_EDW_PPF.F_PP_PACKAGE_SUBSCRIPTIONS PPSR ON (PPSR.ROOT_SUBS_KEY = PPS.ROOT_SUBS_KEY
				AND PPSR.SUBSCRIPTION_START_DT > PPS.SUBSCRIPTION_START_DT)
		LEFT OUTER JOIN DP_EDW_PPF.D_PP_PACKAGE PPR ON (PPR.PCKG_ID = PPSR.PCKG_ID)
	WHERE PPS.SUBSCRIPTION_END_DT BETWEEN DATE - 90 AND DATE + 30
		AND PP.PCKG_SUB_CATEGORY = 'Monthly'
		AND PP.PCKG_SERVICE_TYPE = 'SAWA'
	QUALIFY Row_Number() Over(PARTITION BY PPS.PCKG_ID, PPS.SUBSCRIPTION_START_DT, PPS.ROOT_SUBS_KEY ORDER BY PPR.PRICE DESC, PPR.PCKG_TYPE) =1 )X
	INNER JOIN DP_EDW_PPF.CBU_Weeks CW ON (CW.calendar_date = X.EXPIRY_DATE)
	INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = X.CUST_KEY)
GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16;



--DP_EDW_PPF_VEW.V_PP_RCHRG_DLY


--CONTEXT

The below query gives basically the daily recharge details 

This query creates a daily SAWA prepaid recharge performance dataset.

It uses daily recharge data and calculates Total Recharge Revenue, broken down by recharge channel, date, customer ID type, nationality, and rate plan.

It covers the recent 3 months and a comparable period from the previous year and only includes active SS prepaid customers.

Main metric: TOTAL_RCHRG = total daily recharge amount.

In simple terms: Daily SAWA recharge revenue by customer and recharge channel.



--SQL QUERY 


SELECT CW.calendar_date REF_DATE,
    CW.LST_DAY_OF_MTH,
    CW.LST_DAY_OF_WK,
    CW.CBU_MONTH_ID,
    CW.CBU_WEEK_ID,
    CW.CBU_MONTH_NUM,
    CW.CBU_WEEK_NUM,
    CW.day_of_month,
    CW.Day_Of_WEEK,
    CASE WHEN CW.day_of_month <= Extract(DAY From DATE - 1) THEN 'Y' ELSE 'N' END MTD_FLAG, 
    CASE WHEN CW.day_of_month = Extract(DAY From DATE - 1) THEN 'Y' ELSE 'N' END FIXED_MTD_FLAG, -- Fixed one Day 
    CASE WHEN CW.LST_Day_Of_MTH = CW.calendar_date THEN CW.calendar_date
            WHEN CW.calendar_date = DATE-1 THEN CW.calendar_date ELSE NULL END Month_End_DT,
    Extract(DAY From CW.LST_Day_of_MTH) Month_Days, 
    CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
        WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P' 
        ELSE 'Others' END ID_TYPE,
    PPB.PROD_NME AS RATEPLAN,
    CASE WHEN RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
    CASE WHEN ID_TYPE = 'S' THEN 'Saudi' ELSE
        CASE WHEN CL.CUST_NAT_CD IN ('Yemen','Bangladesh','India','Pakistan','Sudan',
            'Egypt','Philippines','Syria','Ethiopia','Indonesia','Nepal') THEN CL.CUST_NAT_CD ELSE 'Other' END END NATIONALITY,
    channel,Sum(DLY_RCHRG) TOTAL_RCHRG
FROM ( SEL msisdn MSISDN_,REF_DATE CAL_DATE_, 
			CASE WHEN rech_channel LIKE '%USSD%' THEN 'USSD'
			WHEN rech_channel LIKE '%ATL%' THEN rech_channel||'-'||xtrnl_data_2 
			WHEN xtrnl_data_2 LIKE '%UCC%' THEN 'Universal Credit Card'
			ELSE xtrnl_data_2 end channel,
			amount DLY_RCHRG
		FROM dp_edw_ppf_stg.z_adj_rchrg_dly_smry 
		WHERE (REF_DATE BETWEEN Add_Months(Trunc(DATE - 2,'MM'),-3) AND DATE - 1
			        OR REF_DATE BETWEEN Add_Months(Trunc(DATE - 2,'MM'),-12) AND Add_Months(Trunc(DATE - 2,'MM'),-11) - 1)) RCHG
    INNER JOIN DP_EDW_PPF.CBU_Weeks CW ON (CW.calendar_date = RCHG.CAL_DATE_)
    INNER JOIN DP_EDW_PPF.F_RM_PREPAID_BASE PPB ON (RCHG.MSISDN_ = PPB.ACCS_METH_VAL
                            AND (Cast(RCHG.CAL_DATE_ + 1 AS TIMESTAMP(0)) - INTERVAL '1' SECOND) 
                                BETWEEN PPB.SUBS_PROD_STS_STRT_DTTM AND PPB.SUBS_PROD_STS_END_DTTM)
    INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = PPB.CUST_KEY)
WHERE PPB.SUBS_PROD_STS_TYP_NM NOT LIKE '%Inactive%'
                AND PPB.SCREEN_TYPE = 'SS'
GROUP BY 1,2,3,4,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18;




--	DP_EDW_PPF_VEW.V_PP_RCHRG_MTHLY

THIS QUERY GIVES THE MONTHLY TOTAL RECHARGE DETAILS of the subscribers

--SQL


SELECT CW.LST_DAY_OF_MTH MONTH_END_DT,
    CW.LST_DAY_OF_MTH,
    CW.CBU_MONTH_ID,
    CW.CBU_MONTH_NUM,
	CW.year_of_calendar,
    CASE WHEN Extract(MONTH From CAL_DATE_) <= Extract(MONTH From (Trunc(DATE - 2,'MM') - 1))
                THEN 'Y' ELSE 'N' END AS YTM_FLAG,
    CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
        WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P' 
        ELSE 'Others' END ID_TYPE,
        CASE WHEN PPB.SCREEN_TYPE  = 'SS' THEN 
        CASE WHEN PPB.PROD_NME LIKE '%Ziyara%' THEN 'Ziyarah'
            WHEN PPB.PROD_NME = 'SAWA Postpaid' THEN 'SAWA Postpaid'
            WHEN PPB.PROD_NME = 'Prepaid Voice SAWA Workers' THEN 'SAWA Workers'
            ELSE 'SAWA Regular' END
        ELSE PPB.PROD_NME END AS RATEPLAN,
    CASE WHEN PPB.PROD_NME LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
    CASE WHEN ID_TYPE = 'S' THEN 'Saudi' ELSE
        CASE WHEN CL.CUST_NAT_CD IN ('Yemen','Bangladesh','India','Pakistan','Sudan',
            'Egypt','Philippines','Syria','Ethiopia','Indonesia','Nepal') THEN CL.CUST_NAT_CD ELSE 'Other' END END NATIONALITY,
    CHANNEL,
	Sum(DLY_RCHRG) TOTAL_RCHRG
FROM ( SEL msisdn MSISDN_,REF_DATE CAL_DATE_, 
			CASE WHEN rech_channel LIKE '%USSD%' THEN 'USSD'
			WHEN rech_channel LIKE '%ATL%' THEN rech_channel||'-'||xtrnl_data_2 
			WHEN xtrnl_data_2 LIKE '%UCC%' THEN 'Universal Credit Card'
			ELSE xtrnl_data_2 end channel,
			amount DLY_RCHRG
		FROM dp_edw_ppf_stg.z_adj_rchrg_dly_smry 
		WHERE REF_DATE BETWEEN Add_Months(Trunc(DATE - 2,'MM'),-24) AND Trunc(DATE - 2,'MM') - 1
			   AND REF_DATE >= DATE '2025-01-01') RCHG
    INNER JOIN DP_EDW_PPF.CBU_Weeks CW ON (CW.calendar_date = RCHG.CAL_DATE_)
    INNER JOIN DP_EDW_PPF.F_RM_PREPAID_BASE PPB ON (RCHG.MSISDN_ = PPB.ACCS_METH_VAL
                            AND (Cast(RCHG.CAL_DATE_ + 1 AS TIMESTAMP(0)) - INTERVAL '1' SECOND) 
                                BETWEEN PPB.SUBS_PROD_STS_STRT_DTTM AND PPB.SUBS_PROD_STS_END_DTTM)
    INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = PPB.CUST_KEY)
WHERE PPB.SUBS_PROD_STS_TYP_NM NOT LIKE '%Inactive%'
    AND PPB.SCREEN_TYPE = 'SS'
	--AND CW.calendar_date = CW.LST_DAY_OF_MTH
GROUP BY 1,2,3,4,3,4,5,6,7,8,9,10,11;



--DP_EDW_PPF_VEW.V_PP_RECONN_DORMANCY

--CONTEXT

The Sql Query calculates how many days after dormancy the cust came back as a reconnect. 
also their details such as id_type domestic or ziyara flag.


SHOW VIEW DP_EDW_PPF_vEW.V_PP_RECONN_DORMANCY;

SELECT Y.RGS_DATE AS REF_DATE,
    Y.SCREEN_TYPE,
    Y.DOMESTIC_SUBS_FLAG,
    Y.ID_TYPE,
	Y.BUNDLE_TYPE,
    CASE WHEN RECONN_DORMANCY BETWEEN 0 AND 7 THEN '0-7 Days'
        WHEN RECONN_DORMANCY BETWEEN 8 AND 14 THEN '8-14 Days'
        WHEN RECONN_DORMANCY BETWEEN 15 AND 21 THEN '15-21 Days'
        WHEN RECONN_DORMANCY BETWEEN 22 AND 30 THEN '22-30 Days'
        WHEN RECONN_DORMANCY BETWEEN 31 AND 60 THEN '31-60 Days'
        WHEN RECONN_DORMANCY BETWEEN 61 AND 90 THEN '61-90 Days' 
    ELSE '90+' END DORMANCY_DAYS,
    Count(1) SUBS
FROM (SELECT X.ROOT_SUBS_KEY,
		X.RGS_DATE,
		Lag(X.RGS_DATE) Over (PARTITION BY X.ROOT_SUBS_KEY ORDER BY X.RGS_DATE) AS PRE_RGS_DATE,  -- Previous RGS Date
		X.RGS_DATE - Coalesce(PRE_RGS_DATE, DATE - 1000) RECONN_DORMANCY,
	    'SS' SCREEN_TYPE,
	    CASE WHEN A30.PROD_NME LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
	     CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
	        WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P' 
	        ELSE 'Others' END ID_TYPE,
		CASE WHEN A30.BUNDLE_TYPE IN ('ATL','BTL') THEN A30.BUNDLE_TYPE ELSE 'PAYG' END BUNDLE_TYPE
	FROM
		(SELECT ROOT_SUBS_KEY,
			RGS_DATE
		FROM
		    (SELECT BUN.START_DATE RGS_DATE,
		        PPB.ROOT_SUBS_KEY
		    FROM DP_EDW_PPF.F_RM_PREPAID_BASE PPB
		        INNER JOIN DP_EDW_PPF.BUNDLE BUN ON (BUN.MSISDN = PPB.ACCS_METH_VAL
		                AND (Cast(BUN.START_DATE + 1 AS TIMESTAMP(0)) - INTERVAL '1' SECOND) 
		                    BETWEEN PPB.SUBS_PROD_STS_STRT_DTTM AND PPB.SUBS_PROD_STS_END_DTTM)
		    WHERE PPB.SUBS_PROD_STS_TYP_NM NOT LIKE '%Inactive%'
		        AND BUN.START_DATE BETWEEN DATE - 200 AND DATE - 1
		        AND BUN.REVENUE > 0
		    UNION	
		    SELECT MA.Start_date RGS_DATE,
		        PPB.ROOT_SUBS_KEY
		    FROM DP_EDW_PPF.MBB_Activations MA 
		        INNER JOIN DP_EDW_PPF.F_RM_PREPAID_BASE PPB  ON (MA.MSISDN = PPB.ACCS_METH_VAL
		                AND (Cast(MA.Start_date + 1 AS TIMESTAMP(0)) - INTERVAL '1' SECOND) 
		                    BETWEEN PPB.SUBS_PROD_STS_STRT_DTTM AND PPB.SUBS_PROD_STS_END_DTTM)
		    WHERE MA.Start_date BETWEEN DATE - 200 AND DATE - 1
		        AND MA.price > 0
		        AND PPB.SUBS_PROD_STS_TYP_NM NOT LIKE '%Inactive%'
		    UNION
		    SELECT PPDAB.TXN_DT RGS_DATE,
		        PPDAB.ROOT_SUBS_KEY
		    FROM DP_EDW_PPF.F_PP_DAILY_ACTIVE_BASE PPDAB
		    WHERE PPDAB.TXN_DT BETWEEN DATE - 200 AND DATE - 1
		        AND PPDAB.TXN_REV_ACTL_AMT > 0) CU
		GROUP BY 1,2) X
	INNER JOIN DP_EDW_PPF.F_PP_DAILY_ACTIVE_30 A30 ON (A30.REF_DATE = X.RGS_DATE
				AND A30.ROOT_SUBS_KEY = X.ROOT_SUBS_KEY)
	INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = A30.CUST_KEY))Y
WHERE NOT EXISTS (SELECT SERVICE_ORDER_NUM
					FROM DP_EDW_PPF.F_LINE_SALES FLS
					WHERE FLS.ROOT_SUBS_KEY = Y.ROOT_SUBS_KEY
					AND FLS.FIRST_RG_DATE = Y.RGS_DATE)
	AND Y.RGS_DATE >= DATE - 30
GROUP BY 1,2,3,4,5,6;


--DP_EDW_PPF_VEW.V_PP_REVENUE_MONTHLY_WEEKLY

THIS QUERY GIVES THE MONTHLY AND WEEKLY REVENUES OF RGS BASE IT INCLUDES TOTAL REVENUE, ATL REVENUE, BTL REVENUE AND PAYG_TELECOM_REVENUE 
THE OTHERS REVENUE CAN BE OBTAINED BY TOTAL_REV - ATL_REV - BTL_REV- PAYG_TELECOM_REV 
AND ALSO THE NATIONALITY AND ID TYPE.


--SQL QUERY 


SELECT RA.REF_DATE AS PERIOD_END_DT,
	CASE WHEN RA.MNTHLY_WKLY_FLAG = 'M' THEN CW.CBU_MONTH_ID ELSE CW.CBU_WEEK_ID END PERIOD_ID,
	RA.MNTHLY_WKLY_FLAG,
	CW.year_of_calendar AS YEAR_,
	RA.SCREEN_TYPE,
	CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
		WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P' 
	ELSE 'Others' END ID_TYPE,	
	CASE WHEN ID_TYPE   = 'S' THEN 'Saudi' 
		ELSE CASE WHEN CL.CUST_NAT_CD IN ('Yemen','Bangladesh','India','Pakistan','Sudan',
	'Egypt','Philippines','Syria','Ethiopia','Indonesia','Nepal') THEN CL.CUST_NAT_CD ELSE 'Other' END END NATIONALITY,
	RA.RATEPLAN,
	CASE WHEN RA.RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
	CASE WHEN RA.RGS_30_FLAG = 'Y' THEN 'RGS' ELSE 'NRGS' END RGS_FLAG,
	CASE WHEN RA.SCREEN_TYPE = 'SS' THEN 
		CASE WHEN RGS_FLAG = 'RGS' THEN 
			CASE WHEN PP.PCKG_TYPE = 'ATL' THEN '01. ATL'
				WHEN PP.PCKG_TYPE = 'BTL' THEN '02. BTL'
				WHEN PP.PCKG_TYPE = 'Prorated Bundle Dormant' THEN '04. Prorated Bundle Dormant'
			ELSE '05. PAYG' END
				ELSE '06. NRGS' END ELSE 'NA' END BUNDLE_TYPE,	
				
	CASE WHEN RA.SCREEN_TYPE = 'SS' THEN 
		CASE WHEN RGS_FLAG = 'RGS' THEN 
			CASE WHEN PP.PCKG_TYPE = 'BTL' THEN '13. BTL' 
				WHEN PP.PCKG_TYPE = 'Prorated Bundle Dormant' THEN '15. Prorated Bundle Dormant' 
				WHEN PP.PCKG_TYPE = 'ATL' THEN 
					CASE WHEN PP.PCKG_NAME LIKE '%FLEX%100%' THEN '10. Sawa Flex 100'
						WHEN PP.PCKG_NAME LIKE '%SAWA%FLEX%' THEN '11. Sawa Flex Others'
						WHEN PP.PCKG_NAME LIKE '%LIKE%' THEN '05. Sawa Like & Like+'
						WHEN PP.PCKG_NAME LIKE '%POST%' THEN '03. Sawa Post & Post+'
						WHEN PP.PCKG_NAME LIKE '%STAR%' THEN '02. Sawa Star & Star+'
						WHEN PP.PCKG_NAME LIKE '%SHARE%' THEN '04. Sawa Share & Share+'
						WHEN PP.PCKG_NAME LIKE '%HERO%' THEN '01. Sawa Hero'
						WHEN PP.PCKG_NAME LIKE '%CAPTAIN%' THEN '06. Sawa Captain'
						WHEN PP.PCKG_NAME LIKE '%BASIC%' THEN '07. Sawa Basic'
						WHEN PP.PCKG_NAME LIKE '%SAWA%150%' THEN '08. Sawa 150'
						WHEN PP.PCKG_NAME LIKE '%SAWA%175%' THEN '09. Sawa 175'
					ELSE '12. Other ATLs' END
			ELSE '14. PAYG' END
		ELSE '16. NRGS' END 
	ELSE 'NA' END BUNDLES_GROUP_1,	
	
	CASE WHEN RA.SCREEN_TYPE = 'SS' THEN 
		CASE WHEN RGS_FLAG = 'RGS' THEN 
			CASE WHEN PP.PCKG_TYPE IN ('ATL','BTL') THEN Coalesce(PP.PCKG_GROUP_1,'90. Unknown Bundle')
				WHEN PP.PCKG_TYPE = 'Prorated Bundle Dormant' THEN '98. Prorated Bundle Dormant'
			ELSE '97. PAYG' END
				ELSE '99. NRGS' END ELSE 'NA' END BUNDLE_GROUP_2,	

	CASE WHEN RA.SCREEN_TYPE = 'LS' THEN 'Undefined' ELSE
		CASE WHEN Coalesce(RA.SALES_COHORT_MONTH,'00') IN ('00','01','02') THEN 'New Sales' 
	        WHEN Coalesce(RA.SALES_COHORT_MONTH,'00') NOT IN ('00','01','02') THEN
	            CASE WHEN Coalesce(RA.CNT_LAST_4MS_CU,0) = 4 THEN 'Core Base'
	                ELSE 'Non-Core Base' END 
	        ELSE 'Undefined' END END CORE_SEG, 

	CASE WHEN RAP.ROOT_SUBS_KEY IS NULL AND FLS.ROOT_SUBS_KEY IS NOT NULL THEN 'New Sales'
		WHEN RAP.ROOT_SUBS_KEY IS NULL AND FLS.ROOT_SUBS_KEY IS NULL THEN 'Reconnect'
		ELSE 'Continued Base' END BASE_CATEGORY,

	Sum(RA.TOTAL_REV) TOTAL_REVENUE,
	Sum(RA.ATL_REV) ATL_REVENUE,
	Sum(RA.BTL_REV) BTL_REVENUE,
	Sum(RA.PAYG_TELECOM_REV) PAYG_TELECOM_REV,
	Sum(CASE WHEN RA.PERIOD_END_ACT_FLAG = 'Y' AND RA.RGS_30_FLAG = 'Y' THEN 1 ELSE 0 END) ARPU_BASE
FROM DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RA
	INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = RA.CUST_KEY)
	INNER JOIN DP_EDW_PPF.CBU_Weeks CW ON (CW.calendar_date = RA.REF_DATE)
	LEFT OUTER JOIN DP_EDW_PPF.D_PP_PACKAGE PP ON (PP.PCKG_ID = RA.BUNDLE_NAME)
	LEFT OUTER JOIN DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RAP ON (RAP.ROOT_SUBS_KEY = RA.ROOT_SUBS_KEY
			AND RAP.REF_DATE = Trunc(RA.REF_DATE,'MM') - 1
			AND RAP.PERIOD_END_ACT_FLAG = 'Y'
			AND RAP.MNTHLY_WKLY_FLAG = 'M'
			AND RAP.RGS_30_FLAG = 'Y')
	LEFT OUTER JOIN DP_EDW_PPF.F_LINE_SALES FLS ON (FLS.ROOT_SUBS_KEY = RA.ROOT_SUBS_KEY
				AND Last_Day(FLS.ORDER_END_DT) = RA.REF_DATE
				AND FLS.SALES_FLAG = 'Sales')
WHERE RA.REF_DATE BETWEEN Add_Months(Trunc((DATE - 1),'MM'),-23) AND DATE - 1
	AND RA.REF_DATE >= DATE '2025-01-01'
	--AND RA.ACTIVE_30_FLAG = 'Y'
	AND RA.SCREEN_TYPE = 'SS'
	--AND RA.MNTH_END_ACT_FLAG = 'Y'
	AND RA.MNTHLY_WKLY_FLAG = 'M'
GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15;



-- DP_EDW_PPF_VEW.V_PP_RGS_HARD_CHURN_DLY


THIS QUERY CALCULATES THE HARD CHURNED SUBSCRIBERS DAILY 

SELECT CW.calendar_date REF_DATE,
	CW.LST_DAY_OF_MTH, 
    CW.CBU_MONTH_ID,
    CW.CBU_WEEK_ID,
    CW.CBU_MONTH_NUM,
    CW.day_of_month,
	FLC.ORDER_SUBTYP_NME,
	FLC.SCREEN_TYPE,
    CASE WHEN CW.day_of_month <= Extract(DAY From DATE - 1) THEN 'Y' ELSE 'N' END MTD_FLAG,
	CASE WHEN FLC.RATE_PLAN_NME LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
	CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
        WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P' 
        ELSE 'Others' END ID_TYPE,
    CASE WHEN ID_TYPE = 'S' THEN 'Saudi' ELSE
        CASE WHEN CL.CUST_NAT_CD IN ('Yemen','Bangladesh','India','Pakistan','Sudan',
            'Egypt','Philippines','Syria','Ethiopia','Indonesia','Nepal') THEN CL.CUST_NAT_CD ELSE 'Other' END END NATIONALITY,
	CASE WHEN A30.RGS_30_FLAG = 'Y' THEN 'RGS' ELSE 'NRGS' END RGS_30,
	CASE WHEN Coalesce(LCA.LINE_TENURE,-9999) = -9999 THEN 'UNKNOWN' ELSE
		CASE WHEN Coalesce(LCA.LINE_TENURE,-9999) < 90 THEN '1. NEW LINE'
		WHEN Coalesce(LCA.LINE_TENURE,-9999) BETWEEN 90 AND 180 THEN '2. 90 - 180'
		WHEN Coalesce(LCA.LINE_TENURE,-9999) BETWEEN 180 AND 360 THEN '3. 180 - 360'
		WHEN Coalesce(LCA.LINE_TENURE,-9999) BETWEEN 360 AND 1080 THEN '4. 360 - 1080'
		WHEN Coalesce(LCA.LINE_TENURE,-9999) BETWEEN 1080 AND 1800 THEN '5. 1080 -1800'
		ELSE  '6. > 1800' END END LINE_TENURE,
	LCA.MNP_TO_OPR TO_OPERATOR,
	CASE WHEN Coalesce(RA.SALES_COHORT_MONTH,'00') IN ('00','01','02') THEN 'New Sales' 
	        WHEN Coalesce(RA.SALES_COHORT_MONTH,'00') NOT IN ('00','01','02') THEN
	            CASE WHEN Coalesce(RA.CNT_LAST_4MS_CU,0) = 4 THEN 'Core Base'
	                ELSE 'Non-Core Base' END 
	        ELSE 'Undefined' END CORE_SEG,
	Count(1) CHURN
FROM DP_EDW_PPF.F_LINE_CHURN FLC
	INNER JOIN DP_EDW_PPF.F_LINE_CHURN_ATTR LCA ON (LCA.SERVICE_ORDER_NUM = FLC.SERVICE_ORDER_NUM)
	INNER JOIN DP_EDW_PPF.CBU_Weeks CW ON (CW.calendar_date = FLC.ORDER_END_DT)
	LEFT OUTER JOIN DP_EDW_PPF.F_PP_DAILY_ACTIVE_30 A30 ON (A30.ROOT_SUBS_KEY = FLC.ROOT_SUBS_KEY
				AND FLC.ORDER_END_DT - 1 = A30.REF_DATE)
	LEFT OUTER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = FLC.CUST_KEY)
	LEFT OUTER JOIN DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RA ON (RA.ROOT_SUBS_KEY = FLC.ROOT_SUBS_KEY
				AND RA.REF_DATE = Trunc(FLC.ORDER_END_DT,'MM') - 1
				AND RA.MNTHLY_WKLY_FLAG = 'M'
				AND RA.PERIOD_END_ACT_FLAG = 'Y')
WHERE FLC.LINE_TYPE = 'PP'
	AND FLC.CHURN_FLAG = 'Churn'
	AND (FLC.ORDER_END_DT BETWEEN Add_Months(Trunc(DATE - 2,'MM'),-3) AND DATE - 1)
GROUP BY 1,2,3,4,3,4,5,6,7,8,9,10,11,12,13,14,15,16;



--DP_EDW_PPF_VEW.V_PP_RGS1D_DAILY_BASE


THIS QUERY CALCULATES THE 1 DAY RGS BASE THAT IS REVENUE GENERATING ON THE SAME DAY.


SELECT A30.REF_DATE,
    A30.ROOT_SUBS_KEY,
	A30.ACCS_METH_KEY,
	A30.CUST_KEY,
	Coalesce(A30.WL_BUNDLE_TYPE,'PAYG') OFFER_TYPE,
	Coalesce(A30.WL_BUNDLE_NAME,'PAYG') OFFER_NAME,
	'SS' SCREEN_TYPE
FROM DP_EDW_PPF.F_PP_DAILY_ACTIVE_30 A30
WHERE A30.REF_DATE >= DATE - 30
    AND A30.RGS_1D_FLAG = 'Y';
	
	
	
--DP_EDW_PPF_VEW.V_PP_RGS7D_WEEKLY_BASE

THIS QUERY IS CALCULATING THE REVENUE GENERATING SubscribeRS WEEKLY (7 DAYS)

--SQL

SELECT CW.calendar_date AS REF_DATE,
	PPB.ROOT_SUBS_KEY,
	AM.ACCS_METH_ID ACCS_METH_KEY,
	PPB.CUST_KEY,
	'SS' AS SCREEN_TYPE
FROM DP_EDW_PPF.CBU_Weeks CW
        INNER JOIN DP_EDW_PPF.F_RM_PREPAID_BASE PPB ON (
            (Cast(CW.calendar_date + 1 AS TIMESTAMP(0)) - INTERVAL '1' SECOND) 
                BETWEEN PPB.SUBS_PROD_STS_STRT_DTTM AND PPB.SUBS_PROD_STS_END_DTTM)
		INNER JOIN DP_TAB_VEW.ACCS_METH AM ON (AM.ACCS_METH_VAL = PPB.ACCS_METH_VAL)
WHERE CW.calendar_date BETWEEN DATE  - 50 AND DATE -1
    AND CW.LST_DAY_OF_WK = CW.calendar_date
    AND PPB.SUBS_PROD_STS_TYP_NM NOT LIKE '%Inactive%'
    AND EXISTS (SELECT A30.ROOT_SUBS_KEY
                FROM DP_EDW_PPF.F_PP_DAILY_ACTIVE_30 A30
                WHERE A30.REF_DATE >= DATE - 60
                    AND A30.RGS_1D_FLAG = 'Y'
                    AND A30.ROOT_SUBS_KEY = PPB.ROOT_SUBS_KEY
                    AND A30.REF_DATE BETWEEN CW.LST_DAY_OF_WK - 6 AND CW.LST_DAY_OF_WK)
QUALIFY Row_Number() Over(PARTITION BY REF_DATE,ACCS_METH_KEY ORDER BY PPB.SUBS_STRT_DTTM DESC, PPB.SUBS_PROD_STS_STRT_DTTM DESC) = 1;


---DP_EDW_PPF_VEW.V_PP_SAWA_PCKG_MTHLY


SELECT CW.CBU_MONTH_ID,
    CW.CBU_WEEK_ID,
	CW.LST_DAY_OF_MTH,
	CW.LST_DAY_OF_WK,
    CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
        WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P' 
        ELSE 'Others' END ID_TYPE,
    CASE WHEN ID_TYPE = 'S' THEN 'Saudi' ELSE
        CASE WHEN CL.CUST_NAT_CD IN ('Yemen','Bangladesh','India','Pakistan','Sudan',
            'Egypt','Philippines','Syria','Ethiopia','Indonesia','Nepal') THEN CL.CUST_NAT_CD ELSE 'Other' END END NATIONALITY,
    PP.PCKG_TYPE,
    CASE WHEN PP.PCKG_SUB_CATEGORY IN ('Monthly','Daily','Weekly') THEN PP.PCKG_SUB_CATEGORY ELSE 'Others' END VALIDTY, 
    PP.PCKG_GROUP_1,
    PP.PRICE_RANGE,
	CASE WHEN PP.PCKG_TYPE = 'ATL' THEN
		CASE WHEN PP.PCKG_NAME LIKE '%FLEX%100%' THEN '10. Sawa Flex 100'
			WHEN PP.PCKG_NAME LIKE '%FLEX%' THEN '11. Sawa Flex Others'
			WHEN PP.PCKG_NAME LIKE '%LIKE%' THEN '05. Sawa Like & Like+'
			WHEN PP.PCKG_NAME LIKE '%POST%' THEN '03. Sawa Post & Post+'
			WHEN PP.PCKG_NAME LIKE '%STAR%' THEN '02. Sawa Star & Star+'
			WHEN PP.PCKG_NAME LIKE '%SHARE%' THEN '04. Sawa Share & Share+'
			WHEN PP.PCKG_NAME LIKE '%HERO%' THEN '01. Sawa Hero'
			WHEN PP.PCKG_NAME LIKE '%CAPTAIN%' THEN '06. Sawa Captain'
			WHEN PP.PCKG_NAME LIKE '%BASIC%' THEN '07. Sawa Basic'
			WHEN PP.PCKG_NAME LIKE '%SAWA%150%' THEN '08. Sawa 150'
			WHEN PP.PCKG_NAME LIKE '%SAWA%175%' THEN '09. Sawa 175'
		ELSE '12. Other ATLs' END ELSE PP.PCKG_TYPE END AS GROUP_2,
	PPS.CHANNEL,
	CASE WHEN PPS.RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
    CASE WHEN PPS.SCREEN_TYPE  = 'SS' THEN 
		CASE WHEN PPS.RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah'
			WHEN PPS.RATEPLAN = 'SAWA Postpaid' THEN 'SAWA Postpaid'
			WHEN PPS.RATEPLAN = 'Prepaid Voice SAWA Workers' THEN 'SAWA Workers'
			ELSE 'SAWA Regular' END
		ELSE PPS.RATEPLAN END AS RATE_PLAN,
    Sum(PPS.SUBSCRIPTION_REVENUE) REVENUE,
    Sum(PPS.SUBSCRIPTION_CNT) ACTIVATIONS
FROM DP_EDW_PPF.F_PP_PACKAGE_SUBSCRIPTIONS PPS
	INNER JOIN DP_EDW_PPF.D_PP_PACKAGE PP ON (PP.PCKG_ID = PPS.PCKG_ID)
	INNER JOIN DP_EDW_PPF.D_PP_PACKAGE_SRC_LKP PSL ON (PSL.SRC_SYS_CODE = PPS.PACKAGEX
				AND PSL.DATA_SOURCE_SYSTEM = PPS.DATA_SOURCE
				AND PPS.SUBSCRIPTION_START_DT BETWEEN PSL.REC_START_DT AND PSL.REC_END_DT)
    INNER JOIN DP_EDW_PPF.CBU_Weeks CW ON (CW.calendar_date = PPS.SUBSCRIPTION_START_DT)
    INNER JOIN DP_EDW_SMBB_VEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = PPS.CUST_KEY)
WHERE PP.PCKG_SERVICE_TYPE = 'SAWA'
	AND PPS.SUBSCRIPTION_START_DT BETWEEN Add_Months(Trunc(DATE,'MM'),-18) AND  ((DATE + (7 - DayOfWeek(DATE)))-7)
GROUP BY 1,2,3,4,3,4,5,6,7,8,9,10,11,12,13,14;



--DP_EDW_PPF_VEW.V_PP_SS_RGS_CHUNR_3M



-- SQL QUERY 
SELECT Last_Day(Add_Months(REF_DATE + 1,2)) CHURN_MONTH,
    CASE WHEN CL.CUST_IDENT_SUB_TYP_NME IN ('S','I') THEN CL.CUST_IDENT_SUB_TYP_NME
    	WHEN CL.CUST_IDENT_SUB_TYP_NME = '    جواز سںر زائر و دبلوماسيين ' THEN 'P' 
    ELSE 'Others' END ID_TYPE,
	RA.RATEPLAN,
	CASE WHEN RATEPLAN LIKE '%Ziyara%' THEN 'Ziyarah Subscriber' ELSE 'Domestic Subscriber' END DOMESTIC_SUBS_FLAG,
	RA.ROOT_SUBS_KEY,
	RA.ACCS_METH_KEY,
	RA.ACCNT_KEY,
	RA.CUST_KEY
FROM DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RA
	INNER JOIN DP_EDW_SMBB_vEW.DBB_CUSTOMER_LATEST CL ON (CL.CUST_KEY = RA.CUST_KEY)
WHERE RA.MNTHLY_WKLY_FLAG = 'M'
	AND RA.PERIOD_END_ACT_FLAG = 'Y'
	AND RA.SCREEN_TYPE = 'SS'
	AND RA.RGS_30_FLAG = 'Y'
	AND RA.REF_DATE <= Add_Months(Trunc(DATE,'MM'),-3) - 1
	AND NOT EXISTS (SELECT RAN.ROOT_SUBS_KEY
					FROM DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION RAN
					WHERE RAN.ROOT_SUBS_KEY = RA.ROOT_SUBS_KEY
						AND RAN.REF_DATE BETWEEN Last_Day(Add_Months(RA.REF_DATE + 1,0)) AND Last_Day(Add_Months(RA.REF_DATE + 1,2))
						AND RAN.RGS_30_FLAG = 'Y'
						AND RAN.PERIOD_END_ACT_FLAG = 'Y');
						

		
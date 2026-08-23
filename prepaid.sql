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

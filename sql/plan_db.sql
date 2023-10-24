--- Create Meile Plan Table

CREATE TABLE meile_plans (uuid VARCHAR(100), subscription_id UNSIGNED BIGINT, plan_id UNSIGNED BIGINT, plan_name VARACHAR(256), plan_price UNSIGNED BIGINT, plan_denom VARCHAR(6), PRIMARY KEY(uuid))
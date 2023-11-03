--- Create Meile Plan Table

CREATE TABLE meile_plans (uuid VARCHAR(100), subscription_id UNSIGNED BIGINT, plan_id UNSIGNED BIGINT, plan_name VARACHAR(256), plan_price UNSIGNED BIGINT, plan_denom VARCHAR(100), PRIMARY KEY(uuid))

--- Create Meile Subscriber Table
CREATE TABLE meile_subscriptions (id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, uuid VARCHAR(100), wallet VARCHAR(100), subscription_id UNSIGNED BIGINT, plan_id UNSIGNED BIGINT,  amt_paid DECIMAL(24,12), amt_denom VARCHAR(100), subscribe_date TIMSTAMP, subscription_duration UNSIGNED SMALLINT, expires TIMESTAMP, PRIMARY KEY(id))
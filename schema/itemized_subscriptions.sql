CREATE TABLE itemized_subscriptions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    wallet VARCHAR(100) NULL,
    plan_id BIGINT UNSIGNED NULL,
    amt_paid DECIMAL(24, 12) NULL,
    amt_denom VARCHAR(10) NULL,
    subscribe_date TIMESTAMP NULL,
    subscription_duration SMALLINT UNSIGNED NULL,
    PRIMARY KEY (id)
);
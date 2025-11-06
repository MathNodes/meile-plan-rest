import pymysql
import uuid
from datetime import datetime, timedelta
import scrtxxs

def get_user_input():
    user_input = {}
    user_input['uuid'] = input("Enter UUID: ")
    user_input['wallet'] = input("Enter wallet: ")
    user_input['subscription_id'] = input("Enter subscription ID: ")
    user_input['plan_id'] = input("Enter plan ID: ")
    user_input['amt_paid'] = input("Enter amount paid: ")
    user_input['amt_denom'] = input("Enter amount denomination: ")
    user_input['subscription_duration'] = input("Enter subscription duration (in months): ")
    return user_input

def connect_to_db():
    return pymysql.connect(host=scrtxxs.MySQLHost,
                         port=scrtxxs.MySQLPort,
                         user=scrtxxs.MySQLUsername,
                         passwd=scrtxxs.MySQLPassword,
                         db=scrtxxs.MySQLDB,
                         charset='utf8mb4',
                         cursorclass=pymysql.cursors.DictCursor)

def check_and_insert_or_update(db, user_input):
    cursor = db.cursor()

    # Check if an entry exists for the wallet
    check_query = "SELECT * FROM your_table WHERE wallet = %s"
    cursor.execute(check_query, (user_input['wallet'],))
    result = cursor.fetchone()

    if result:
        # If entry exists, perform an update
        update_query = """
        UPDATE your_table
        SET uuid = %s, subscription_id = %s, plan_id = %s, amt_paid = %s, amt_denom = %s, subscription_duration = %s
        WHERE wallet = %s
        """
        cursor.execute(update_query, (
            user_input['uuid'], user_input['subscription_id'], user_input['plan_id'],
            user_input['amt_paid'], user_input['amt_denom'], user_input['subscription_duration'],
            user_input['wallet']
        ))
    else:
        # If entry does not exist, perform an insert
        subscribe_date = datetime.now()
        expires_date = subscribe_date + timedelta(days=int(user_input['subscription_duration']) * 30)
        insert_query = """
        INSERT INTO your_table (uuid, wallet, subscription_id, plan_id, amt_paid, amt_denom, subscribe_date, subscription_duration, expires, active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
        """
        cursor.execute(insert_query, (
            user_input['uuid'], user_input['wallet'], user_input['subscription_id'],
            user_input['plan_id'], user_input['amt_paid'], user_input['amt_denom'],
            subscribe_date, user_input['subscription_duration'], expires_date
        ))

    db.commit()
    cursor.close()

def main():
    user_input = get_user_input()
    db = connect_to_db()
    check_and_insert_or_update(db, user_input)
    db.close()

if __name__ == "__main__":
    main()
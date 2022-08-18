#!/usr/bin/env python3

#
# Python worker reads data from a Redis cache and writes it to a relational database
# The relational database can be either DB2 or Postgres
# In the case of DB2, the method of connection can be either ODBC or REST
# The behavior is configurable via environment variable settings
#
# Following are redis related environment variables
# Variable name     Desc
# -------------     -----
# REDIS_HOST        OCP service name, hostname, or ip address  (default: "redis")
# REDIS_PASSWORD    Redis password (default: password)
#
# Following are valid database-related environment variable scenarios
#
# For Postgres
# Variable name     Desc
# -------------     -----
# WHICH_DBM         Has to be exactly "POSTGRES"
# PG_HOSTNAME       OCP service name, hostname, or ip address  (default: "postgresql")
# PG_DATABASE       Postgres database name (default: "db")
# PG_USER           Postgres database userid (default: "admin")
# PG_PASSWORD       Postgres database password (default: "admin")
#
# For DB2 via ODBC
# Variable name     Desc
# -------------     -----
# WHICH_DBM         Has to be exactly "DB2"
# DB2_METHOD        Has to be exactly "ODBC"
# DB2_DRIVER        Driver name (default: "IBM DB2 ODBC DRIVER")
# DB2_DATABASE      Database name (default: "SAMPLEDB")
# DB2_HOSTNAME      Hostname or ip address (default: "localhost")
# DB2_PORT          Port number (default: "50000")
# DB2_PROTOCOL      Protocol the driver should use (default: "TCPIP")
# DB2_SCHEMA        Database table schema name (default: "TEAM1")
# DB2_USER          Database user (default: "db2inst1")
# DB2_PASSWORD      Database password (default: "passw0rd")
# 
# For DB2 via REST  (only basic auth is supported)
# Variable name     Desc
# -------------     -----
# WHICH_DBM         Has to be exactly "DB2"
# DB2_METHOD        Has to be exactly "REST"
# DB2_REST_APIURL   The Rest API URL - For example http://9.60.87.140:5040/services/TEA1VoteService/tea1writevote
# DB2_USER          Database user (default: "IBMUSER")
# DB2_PASSWORD      Database password (default: "SYS1")
#
# Setting the DEBUG_LOGGING environment variable to "True" will produce some additional log messages that can be
# helpful when trying to debug the DB2 via REST connection.  The setting can be "True" or "False"  (defualt: False)
#

from redis import Redis
import os
import time
import psycopg2
import ibm_db
import requests
import json

debug_logging = os.environ.get('DEBUG_LOGGING', False)
which_dbm = os.environ.get('WHICH_DBM', 'DB2')  # DB2 or POSTGRES
if which_dbm == 'DB2':
    db2_method = os.environ.get('DB2_METHOD', 'ODBC') # ODBC or REST
    db2_schema = os.environ.get('DB2_SCHEMA', 'TEAM1')

def get_redis():
    redis_host     = os.environ.get('REDIS_HOST', 'redis')
    redis_password = os.environ.get('REDIS_PASSWORD', 'password')
    print ("Connecting to Redis using hostname: " + redis_host)
    redis_conn = Redis(host=redis_host, db=0, socket_timeout=5, password=redis_password)
    redis_conn.ping()
    print ("Connected to redis!")
    return redis_conn

def connect_db2():
    if db2_method == 'ODBC':
        dsn_dr  = os.environ.get('DB2_DRIVER', 'IBM DB2 ODBC DRIVER')
        dsn_db  = os.environ.get('DB2_DATABASE','SAMPLEDB')
        dsn_hn  = os.environ.get('DB2_HOSTNAME','localhost')
        dsn_pt  = os.environ.get('DB2_PORT', '50000')
        dsn_prt = os.environ.get('DB2_PROTOCOL', 'TCPIP')
        dsn_uid = os.environ.get('DB2_USER', 'db2inst1')
        dsn_pw  = os.environ.get('DB2_PASSWORD', 'passw0rd')

        dsn = (
            "DRIVER={0};"
            "DATABASE={1};"
            "HOSTNAME={2};"
            "PORT={3};"
            "PROTOCOL={4};"
            "UID={5};"
            "PWD={6};").format(dsn_dr, dsn_db, dsn_hn, dsn_pt, dsn_prt, dsn_uid, dsn_pw)

        try:
            print ("connecting to the DB2 using connect string: " + dsn)
            conn = ibm_db.connect(dsn, "", "")
            print ("Successfully connected to DB2")
            
            return conn 

        except Exception as e:
            print ("error connecting to the DB2")
            print (e)

    elif db2_method == 'REST':
        db2_restapiurl=os.environ.get('DB2_REST_APIURL', '')
        return db2_restapiurl

def create_db2_table():
    try: 
        conn = connect_db2()

    except Exception as e:
        print ("error connecting to DB2")  
        print (str(e)) 

    try:
        cmd = ("CREATE TABLE IF NOT EXISTS {0}.VOTES (ID VARCHAR(255) NOT NULL, VOTE VARCHAR(255) NOT NULL)").format(db2_schema)
        ibm_db.exec_immediate(conn, cmd)
        print ("votes table created") 

    except Exception as e:
        print ("error creating database table")
        print (e)

    try:
        ibm_db.close(conn)

    except Exception as e:
        print ("error closing connection to DB2")
        print (str(e))

def insert_db2(data):
    if db2_method == 'ODBC':
        try:
            conn = connect_db2()

        except Exception as e:
            print ("error connecting to DB2")  
            print (str(e)) 


        try:
            insert_sql = ("INSERT INTO {0}.VOTES VALUES (?, ?)").format(db2_schema)
            params = data.get("voter_id"),data.get("vote")
            prep_stmt = ibm_db.prepare(conn, insert_sql)
            ibm_db.execute(prep_stmt, params)
        
            print ("row inserted into DB")

        except Exception as e:
            print ("error inserting into DB2")
            print (str(e))

        try:
            ibm_db.close(conn)

        except Exception as e:
            print ("error closing connection to DB2")
            print (str(e))

    elif db2_method == 'REST':
        try:
            conn = connect_db2()
        
        except Exception as e:
            print ("error connecting to DB2")
            print (str(e))

        try:
            headers = {'Content-type': 'application/json', 'Accept': '*/*'}
            id = data.get("voter_id")
            vote = data.get("vote")
            body = {"voterid" : id, "voted" : vote}
            userid = os.environ.get('DB2_USER', 'IBMUSER')
            password = os.environ.get('DB2_PASSWORD', 'SYS1')

            if debug_logging:
                print("Attempting to connect to URL:" + conn)
                print("Headers=" + json.dumps(headers))
                print("data=" + json.dumps(body))
                print("userid=" + userid + " password=" + password)

            response = requests.post(conn, json=body, headers=headers, auth=(userid, password))
            
            if debug_logging:
                print("response.status_code=" + str(response.status_code))
                print("response=" + response.text)

            if response.status_code != 200:
                print ("Unexpected response received inserting into DB2:" + str(response.status_code))

        
        except Exception as e:
            print ("Error inserting into DB2")
            print (str(e))

def connect_pg():
    pg_hostname = os.environ.get('PG_HOSTNAME', "postgresql")
    pg_database = os.environ.get('PG_DATABASE', "db") 
    pg_user     = os.environ.get('PG_USER', "admin") 
    pg_password = os.environ.get('PG_PASSWORD', "admin") 

    try:
        print ("Connecting to the Postgres database") 
        conn = psycopg2.connect ("host={} dbname={} user={} password={}".format(pg_hostname, pg_database, pg_user, pg_password))
        print ("Successfully connected to Postgres")
      
        return conn 

    except Exception as e:
        print ("Error connecting to the Postgres database")
        print (e)

def create_pg_table():
    try: 
        conn = connect_pg()

    except Exception as e:
        print ("Error connecting to Postgres database")  
        print (str(e)) 

    try:
        cursor = conn.cursor()
        sqlCreateTable = "CREATE TABLE IF NOT EXISTS public.votes (id VARCHAR(255) NOT NULL, vote VARCHAR(255) NOT NULL);"
        cursor.execute(sqlCreateTable)
        print ("votes table created") 
        conn.commit()
        cursor.close() 

    except Exception as e:
        print ("Error creating Postgres database table")
        print (e)

    try:
        conn.close()

    except Exception as e:
        print ("Error closing connection to Postgres database")
        print (str(e))

def insert_pg(data):
    try:
        conn = connect_pg()

    except Exception as e:
        print ("Error connecting to Postgres database")  
        print (str(e)) 

    try:
        cur = conn.cursor()
        cur.execute("insert into votes values (%s, %s)", (data.get("voter_id"), data.get("vote")))
        conn.commit()
        print ("Row inserted into Postgres database")
        cur.close()

    except Exception as e:
        conn.rollback()
        cur.close()
        print ("Error inserting into Postgres database")
        print (str(e))

    try:
        conn.close()

    except Exception as e:
        print ("Error closing connection to Postgres database")
        print (str(e))

def create_table():
    if which_dbm == 'DB2' and db2_method == 'ODBC':
        create_db2_table()
    else:
        create_pg_table()

def process_votes():
    redis = get_redis()
    redis.ping()  
    while True: 
        try:  
            msg = redis.rpop("votes")
            if debug_logging:
                print(msg)
            if (msg != None): 
                print ("Reading message from redis")
                msg_dict = json.loads(msg)
                # will look like this
                # {"vote": "a", "voter_id": "71f0caa7172a84eb"}
                if which_dbm == 'DB2':
                    insert_db2(msg_dict)
                else:
                    insert_pg(msg_dict) 
            time.sleep(5)        
   
        except Exception as e:
            print(e)

def validate_env():
    
    if not which_dbm in ['DB2', 'POSTGRES']:
        print("Invalid setting for WHICH_DBM env variable.  Should be DB2 or POSTGRESS.")
        return False
    if which_dbm == 'DB2':
        if not db2_method in ['ODBC', 'REST']:
            print("Invalid setting for DB2_METHOD env variable.  Should be ODBC or REST.")
            return False
    return True

if __name__ == '__main__':
    if validate_env:
        create_table()
        process_votes()

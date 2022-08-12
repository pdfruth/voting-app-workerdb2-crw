#!/usr/bin/env python3

from redis import Redis
import os
import time
import ibm_db
import json

db2_schema=os.environ.get('DB2_SCHEMA', 'team1')

def get_redis():
   redishost = os.environ.get('REDIS_HOST', 'new-redis')
   redispassword = os.environ.get('REDIS_PASSWORD', 'password')
   print ("Connecting to Redis using hostname: " + redishost)
   #redis_conn = Redis(host=redishost, db=0, socket_timeout=5)
   redis_conn = Redis(host=redishost, db=0, socket_timeout=5, password=redispassword)
   redis_conn.ping()
   print ("connected to redis!") 
   return redis_conn

def connect_db2(): 
   dsn_dr=os.environ.get('DB2_DRIVER', 'IBM DB2 ODBC DRIVER')
   dsn_db=os.environ.get('DB2_DATABASE','SAMPLEDB')
   dsn_hn=os.environ.get('DB2_HOSTNAME','localhost')
   dsn_pt=os.environ.get('DB2_PORT', '50000')
   dsn_prt=os.environ.get('DB2_PROTOCOL', 'TCPIP')
   dsn_uid=os.environ.get('DB2_USER', 'db2inst1')
   dsn_pw=os.environ.get('DB2_PASSWORD', 'passw0rd')

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

def create_db2_table():
    try: 
       conn = connect_db2()

    except Exception as e:
       print ("error connecting to DB2")  
       print (str(e)) 

    try:
       cmd = ("CREATE TABLE IF NOT EXISTS {0}.votes (id VARCHAR(255) NOT NULL, vote VARCHAR(255) NOT NULL)").format(db2_schema)
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
    try:
       conn = connect_db2()

    except Exception as e:
       print ("error connecting to DB2")  
       print (str(e)) 


    try:
       insert_sql = ("INSERT INTO {0}.votes VALUES (?, ?)").format(db2_schema)
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

def process_votes():
    redis = get_redis()
    redis.ping()  
    while True: 
       try:  
          msg = redis.rpop("votes")
          print(msg)
          if (msg != None): 
             print ("reading message from redis")
             msg_dict = json.loads(msg)
             insert_db2(msg_dict) 
          # will look like this
          # {"vote": "a", "voter_id": "71f0caa7172a84eb"}
          time.sleep(5)        
   
       except Exception as e:
          print(e)

if __name__ == '__main__':
    create_db2_table()
    process_votes()

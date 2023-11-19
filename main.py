import os

from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import (
    create_engine,
    MetaData,
)


from sqlalchemy.orm import sessionmaker

from sqlalchemy.ext.declarative import declarative_base


import sqlite3
from auth import AuthHandler
from schemas import AuthDetails

engine = create_engine("sqlite:///./.venv/server/master.db")
metadata = MetaData()
Base = declarative_base()
Session = sessionmaker(bind=engine)
session = Session()
auth_handler = AuthHandler()
app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:8001",
    "http://localhost:5174",
    "http://localhost:5173",
    "http://localhost:5176",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InventoryUpload(BaseModel):
    file: UploadFile
    username: str


def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Exception as e:
        print(e)

    return conn


def create_username_and_password_table():
    sql_create_username_and_password_table = """ Create TABLE IF NOT EXISTS username_and_password (
                                                 id integer PRIMARY KEY AUTOINCREMENT,
                                                 username text NOT NULL,
                                                 password text NOT NULL
    );"""

    conn = create_connection("./master.db")
    c = conn.cursor()
    c.execute(sql_create_username_and_password_table)
    conn.commit()
    conn.close()


def create_inventory_table(username):
    sql_create_inventory_table = f""" Create TABLE IF NOT EXISTS {username}_inventory (
                                      charName text,
                                      itemLocation text,
                                      itemName text,
                                      itemId integer,
                                      itemCount integer,
                                      itemSlots integer
    );"""

    conn = create_connection("./master.db")
    c = conn.cursor()
    c.execute(sql_create_inventory_table)
    conn.commit()
    conn.close()


def fetch_inventory(username):
    conn = create_connection("./master.db")
    c = conn.cursor()
    query_string = f"""SELECT * from {username}_inventory"""
    c.execute(query_string)
    results = c.fetchall()
    results_array = []

    for result in results:
        item = {}
        item["charName"] = result[0]
        item["itemSlot"] = result[1]
        item["itemName"] = result[2]
        item["itemId"] = result[3]
        item["itemCount"] = result[4]
        item["itemSlots"] = result[5]
        results_array.append(item)

    return results_array


def delete_inventory(user_name, char_name):
    conn = create_connection("./master.db")
    c = conn.cursor()
    query_string = (
        f"""DELETE from {user_name}_inventory WHERE charName = '{char_name}'"""
    )

    c.execute(query_string)
    conn.commit()
    conn.close()


create_username_and_password_table()


@app.post("/signup", status_code=201)
def register(body: dict):
    # Fetch / GET table 'users', and append the col 'usernames' in the list:
    conn = create_connection("./master.db")
    c = conn.cursor()
    c.execute("SELECT username from username_and_password")
    results = c.fetchall()
    users = []

    for user in results:
        users.append(user[0])

    if any(x == body["username"] for x in users):
        raise HTTPException(status_code=400, detail="Username is taken")

    hashed_password = auth_handler.get_password_hash(body["password"])
    query_string = f"INSERT INTO username_and_password (username, password) VALUES ('{body['username']}' , '{hashed_password}')"

    c.execute(query_string)
    conn.commit()
    conn.close()

    return {"username": body["username"], "password": body["password"]}


@app.post("/login")
def login(auth_details: AuthDetails):
    conn = create_connection("./master.db")
    c = conn.cursor()
    query_string = "SELECT username, password FROM username_and_password"
    c.execute(query_string)
    results = c.fetchall()
    conn.commit()
    conn.close()

    found_user = None

    for user in results:
        print(user)
        if user[0] == auth_details.username:
            found_user = {"username": user[0], "hashed_password": user[1]}
            print("found_user: ")
            print(found_user)
            break
    if found_user == None:
        raise HTTPException(status_code=401, detail="Username not found")

    print(
        auth_handler.verify_password(
            auth_details.password, found_user["hashed_password"]
        )
    )
    # We need to GET the hashed password from the SQL db, and pass it as second parameter below where 'found_user' is:
    if (found_user is None) or (
        not auth_handler.verify_password(
            auth_details.password, found_user["hashed_password"]
        )
    ):
        print("debug test")
        raise HTTPException(status_code=401, detail="Invalid password")
    token = auth_handler.encode_token(found_user["username"])

    create_inventory_table(auth_details.username)
    inventory_db = fetch_inventory(auth_details.username)

    return {"token": token, "loggedIn": True, "inventory_db": inventory_db}


@app.get("/istokenvalid")
def protected(username=Depends(auth_handler.auth_wrapper)):
    token = auth_handler.encode_token(username)
    return {"token": token}


@app.post("/uploadfile")
async def parse_inventory_file(request: Request):
    # Batch needs username appended to the front
    form_data = await request.form()
    print(form_data)
    file = form_data["file"]
    filename = form_data["filename"]
    username = form_data["username"]
    # Delete the old inventory
    delete_inventory(username, filename)
    inventory_file_raw = file.file.read()

    inventory_file = inventory_file_raw.decode("utf-8").splitlines()
    batch = []

    for line in inventory_file:
        line = line.strip().split("\t")
        line.insert(0, filename)
        batch.append(line)

    query_string = f"""INSERT INTO {username}_inventory VALUES (?, ?, ?, ?, ?, ?)"""
    conn = create_connection("./master.db")
    c = conn.cursor()
    c.executemany(query_string, batch)
    conn.commit()

    query_string = (
        f"""SELECT * FROM {username}_inventory WHERE charName = '{filename}'"""
    )
    c.execute(query_string)
    results = c.fetchall()
    conn.commit()
    conn.close()

    # convert results to object before sending back to frontend:
    results_array = []

    for result in results:
        item = {}
        item["charName"] = result[0]
        item["itemSlot"] = result[1]
        item["itemName"] = result[2]
        item["itemId"] = result[3]
        item["itemCount"] = result[4]
        item["itemSlots"] = result[5]
        results_array.append(item)

    print(filename)
    print(results)
    return {"file_uploaded": True, "char_inventory": results_array}


@app.get("/fetchinventory/{username}")
async def fetch_inventory_endpoint(username: str):
    inventory_db = fetch_inventory(username)
    return {"inventory_db": inventory_db}


@app.delete("/deletechar")
async def delete_character(body: dict):
    print(body)
    query_string = f"""DELETE from {body['username']}_inventory WHERE charName = '{body['charName']}'"""
    conn = create_connection("./master.db")
    c = conn.cursor()
    c.execute(query_string)
    conn.commit()
    conn.close()
    return {"success": True}

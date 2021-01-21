# Dependencies
import json
import requests
import psycopg2 as psy

# Core variables
api_url_base = "http://www.ebi.ac.uk/ols/api"
header = {"Accept": "application/json"}
size_per_page = "100"  # Number of terms to retrieve in single page GET. MAX Can be 500 according to API Docs
api_url = '{0}/ontologies/efo/terms?page=0&size={1}'.format(api_url_base,size_per_page)
response_json = requests.get(api_url, headers=header).json()
total_pages = response_json['page']['totalPages']  # Total pages of efo terms
table_name = "EFO_MESH"  # Table name where data is to be kept.
database_name = "assessment"  # Name of the database the table_name var belongs to.
database_user = "postgres"  # Database user
database_password = ""  # Database user's password
database_host = "127.0.0.1"  # localhost or 127.0.0.1 for local database
database_port = "5432"  # Port is usually 5432 for psql

# Functions
def create_table():
    try:
        # Providing credentials to connect to db
        conn = psy.connect(
            database = database_name,
            user = database_user,
            password = database_password,
            host = database_host,
            port = database_port
        )
        cursor = conn.cursor()

        # Table creation query
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS
            {0}(SHORT_FORM  VARCHAR(200),
            LABEL  VARCHAR(2000),
            SYNONYMS  VARCHAR(20000),
            PARENTS_LINK VARCHAR(2000),
            MESH_ID  VARCHAR(200),
            MESH_LABEL VARCHAR(2000),
            PRIMARY KEY (SHORT_FORM));
            """.format(table_name)
        )
        conn.commit()  # Commits changes to database
        conn.close()  # Closes the connection to db
        print("Table creation query has been successfully executed")
    except Exception as e:  # In case of any error:
        print(e)  # Print the error
        print("Error connecting to the database or executing the table creation query")

def get_number_of_efo_terms():
    total_elements = response_json['page']['totalElements']  # Total elements of efo terms
    return total_pages,total_elements

def get_mesh_label(mesh_id):
    mesh_label_api = "https://id.nlm.nih.gov/mesh/lookup/label?resource={0}".format(mesh_id)
    label = requests.get(mesh_label_api, headers=header).json()

    if len(label) >= 1:
        return label[0]  # Response of label comes as a list of 1 element i.e. ['Biliary Tract Diseases']
    else:
        return "NA"

def write_to_table(total_pages):
    # Providing credentials to connect to db
    conn = psy.connect(
        database=database_name, 
        user=database_user, 
        password=database_password,
        host=database_host,
        port=database_port
    )
    cursor = conn.cursor()
    # Go to all pages and retrieve all efo terms
    for page_number in range(0,total_pages):
        print("Retrieving and writing page {0}.".format(page_number))
        api_url_page = '{0}/ontologies/efo/terms?page={1}&size={2}'.format(api_url_base, page_number, size_per_page)
        response_page = requests.get(api_url_page, headers=header).json()

        # After getting all the terms of a page write to table
        for terms in response_page['_embedded']['terms']:
            mesh_id,mesh_label = "NA","NA"

            # Gets executed only if terms['obo_xref'] is not none
            if terms['obo_xref']:
                for i in terms['obo_xref']:
                   if i['database'] == "MESH":
                        mesh_id = i['id']
                        mesh_label = get_mesh_label(mesh_id)

            # Inserting the values query
            postgres_insert_query = """
                INSERT INTO {0}(SHORT_FORM, LABEL, SYNONYMS, PARENTS_LINK, MESH_ID,MESH_LABEL) 
                SELECT (%s),(%s),(%s),(%s),(%s),(%s)
                WHERE NOT EXISTS 
                (SELECT SHORT_FORM FROM {1} WHERE SHORT_FORM =(%s));""".format(table_name,table_name)
            short_form,label,synonyms = terms['short_form'], terms['label'] , terms['synonyms']
            try:
                parents_links = terms['_links']['parents']['href']
            except: 
                parents_links = "NA"  # Parents links made as "NA" when not available

            record_to_insert = (short_form, label,synonyms,parents_links,mesh_id,mesh_label,short_form)
            try:
                cursor.execute(postgres_insert_query, record_to_insert)
            except Exception as e:  # In case of ANY error
                print(e)  # Prints the error
                cursor.execute("rollback")  # Causes all the updates made by the transaction to be discarded
            conn.commit()  # Closes the database connection
    conn.close()

# Process initiation
if __name__ == "__main__":
    create_table()
    total_pages,total_elements = get_number_of_efo_terms()  # Gets number of total pages and total number of elements for efo
    print("Total number of pages to retrieve contents is {0}. Total {1} terms are there per page.".format(total_pages,size_per_page))
    write_to_table(total_pages)  # Retrieves and writes data to table
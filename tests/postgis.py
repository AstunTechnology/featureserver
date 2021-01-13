import testing.postgresql
import psycopg2


# Reference to testing.postgresql database instance
db = None

# Connection to the database used to set the database state before running each
# test
db_con = None

# Map of database connection parameters passed to the functions we're testing
db_conf = None


def setup():
    """ Creates a temporary database and sets it up """
    global db, db_con, db_conf
    db = testing.postgresql.Postgresql()
    # Get a map of connection parameters for the database which can be passed
    # to the functions being tested so that they connect to the correct
    # database
    db_conf = db.dsn()
    # Create a connection which can be used by our test functions to set and
    # query the state of the database
    db_con = psycopg2.connect(**db_conf)
    # Commit changes immediately to the database
    db_con.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    reset()
    return (db, db_con, db_conf)


def reset():
    """ Runs the setup sql that should reset the database to a known state """
    with db_con.cursor() as cur:
        # Create the initial database structure (roles, schemas, tables etc.)
        # basically anything that doesn't change
        cur.execute(open('./tests/postgis_setup.sql').read())


def teardown():
    """ Called after all of the tests in this file have been executed to close
    the database connecton and destroy the temporary database """
    db_con.close()
    db.stop()

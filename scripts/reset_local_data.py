import os

if __name__ == '__main__':
    print("WARNING: This will reset all local database data.")
    confirm = input("Type 'YES' to continue: ")
    if confirm == 'YES':
        # In a real environment, this would run alembic downgrade base or DROP schema CASCADE
        print("Resetting data... (mocked)")
        print("Data reset complete.")
    else:
        print("Aborted.")

import psycopg2
from element_fraction_table import get_element_fraction_table, export_to_csv

conn = psycopg2.connect(host='localhost', dbname='alloy_lab', user='postgres', password='<your_password>', options='-c search_path=alloy_lab')
df = get_element_fraction_table(conn)  # or export_to_csv(conn, 'output.csv')
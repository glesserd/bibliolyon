#!/usr/bin/env python3
import requests
import json
import csv
import argparse


class TERMCOLOR:
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    ORANGE = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"


# This could be done dynamically, but the number of bibliothèques
# does change often :)
bibliotheque_codes = {
    "1ARRDT": "1e arrdt",
    "3ARRDT": "3e arrdt - Duguesclin",
    "5STJE": "5e arrdt - St Jean",
    "6ARRDT": "6e arrdt",
    "7GERLA": "7e arrdt - Gerland",
    "7JMACE": "7e arrdt - J. Macé",
    "8ARRDT": "8e arrdt - Bachut",
    "9LDUCH": "9e arrdt - La Duchère",
    "9STRAM": "9e arrdt - St Rambert",
    "9VAISE": "9e arrdt - Vaise",
    "COLLEC": "Prêt aux collectivités",
    "PARTDI": "Part-Dieu",
}


book_statuses = {
    "En rayon": f"{TERMCOLOR.GREEN}En rayon{TERMCOLOR.ENDC}",
    "Réservé": f"{TERMCOLOR.RED}Réservé{TERMCOLOR.ENDC}",
    "En prêt": f"{TERMCOLOR.ORANGE}En prêt{TERMCOLOR.ORANGE}",
    "En commande": f"{TERMCOLOR.ORANGE}En commande{TERMCOLOR.ENDC}",
    "En traitement": f"{TERMCOLOR.ORANGE}En traitement{TERMCOLOR.ENDC}",
    "En transit": f"{TERMCOLOR.ORANGE}En transit{TERMCOLOR.ENDC}",
    "A l'équipement": f"{TERMCOLOR.ORANGE}A l'équipement{TERMCOLOR.ENDC}",
    "NO_BOOK": f"{TERMCOLOR.RED}NO_BOOK{TERMCOLOR.ENDC}",
    "NOT_IN_BML": f"{TERMCOLOR.RED}NOT_IN_BML{TERMCOLOR.ENDC}",
    "ERROR": f"{TERMCOLOR.RED}ERROR{TERMCOLOR.ENDC}",
}


def get_status_raw_from_id(bm_id: str) -> dict:
    url = f"https://catalogue.bm-lyon.fr/in/rest/api/notice?id={bm_id}&locale=fr&aspect=Stock&opac=true"
    rep = requests.get(url)
    return rep.json()


def get_status_from_id(bm_id: str) -> dict:
    raw = get_status_raw_from_id(bm_id)
    if "errorReponse" in raw:
        raise KeyError
    biblio_statuses = {}
    if "monographicCopies" not in raw:
        return biblio_statuses
    for copy in raw["monographicCopies"]:
        for book in copy["children"]:
            biblio_statuses[book["data"]["branch"]] = book["data"]["stat_desc"]
    return biblio_statuses


def get_meta_from_id(bm_id: str) -> dict:
    url = f"https://catalogue.bm-lyon.fr/in/rest/api/notice?id={bm_id}&locale=fr"
    rep = requests.get(url)
    return rep.json()


def get_title_id_from_isbn(isbn: str):
    rep = requests.post(
        "https://catalogue.bm-lyon.fr/in/rest/api/search",
        data=json.dumps(
            {
                "searchType": "all",
                "sf": "*",
                "queryid": "NONE",
                "advancedQuery": {
                    "searchContext": "advancedsearch",
                    "terms": [
                        {
                            "index": "isbn_t",
                            "match": "PHRASE",
                            "logical": "AND",
                            "value": isbn,
                        }
                    ],
                    "limitClause": None,
                    "searchType": "all",
                    "pageSize": 10,
                    "sort": "score",
                    "itemCoverage": None,
                    "dcDateRange": None,
                    "section": "*",
                },
                "fl": "id",
                "order": "score",
                "pageNo": 1,
                "pageSize": 1,
                "locale": "fr",
                "includeFacets": False,
            }
        ),
    )

    rep_json = rep.json()

    if rep_json["numHits"] == 0:
        raise LookupError("Not found")

    if rep_json["numHits"] > 1:
        raise IndexError("Too many results")

    # print(json.dumps(rep_json, indent=2))
    return (
        rep_json["resultSet"][0]["title"][0]["value"],
        rep_json["resultSet"][0]["id"][0]["value"],
    )


def get_availability_book(my_bibliotheque, isbn, bmid=None, title=None):
    status = None
    try:
        if bmid is None or bmid == "" or title == "" or title is None:
            title, bmid = get_title_id_from_isbn(isbn)
        status = get_status_from_id(bmid)
        status = status.get(my_bibliotheque, "NO_BOOK")
    except LookupError:
        return "", "", "NOT_IN_BML"

    return bmid, title, status


def cli_list_biblio(args):
    for code, bib in bibliotheque_codes.items():
        print(f"- {code}:  \t{bib}")


def cli_isbn_info(args):
    title, bmid = get_title_id_from_isbn(args.isbn)
    print("Title:", title)
    print("BMID:", bmid)
    # print(get_availability_book("7GERLA", args.isbn))


def cli_availabilty_csv(args):
    my_bibliotheque = args.biblio

    if args.input_file == "":
        print("Error: please, give an input file")
    if args.output == "":
        output_file = args.input_file
    else:
        output_file = args.output

    fieldnames = ["ISBN", "TITLE", "BMID", "AVAILABLE"]

    books = []
    with open(args.input_file, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            for f in fieldnames:
                if f not in row.keys():
                    raise Exception(f"The following columns are required: {fieldnames}")
            books.append(row)

    for book in books:

        book["BMID"], book["TITLE"], book["AVAILABLE"] = get_availability_book(
            my_bibliotheque, book["ISBN"], book["BMID"], book["TITLE"]
        )

        print(
            f"{book_statuses.get(book['AVAILABLE'], book['AVAILABLE'])} \t{book['TITLE'][:128]}"
        )

    with open(output_file, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for book in books:
            writer.writerow(book)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A script to play with the Bibliothèque Municipalle de Lyon."
    )
    subparsers = parser.add_subparsers()

    description = "List bibliothèques"
    sp = subparsers.add_parser("list_biblio", description=description, help=description)
    sp.set_defaults(func=cli_list_biblio)

    description = "Display some info from an ISBN"
    sp = subparsers.add_parser("isbn_info", description=description, help=description)
    sp.add_argument("isbn", type=str, help="The ISBN to analyze")
    sp.set_defaults(func=cli_isbn_info)

    description = (
        "Get books availabilty from a CSV file where the first column is the ISBN."
    )
    sp = subparsers.add_parser(
        "availabilty_csv", description=description, help=description
    )
    sp.add_argument("input_file", type=str, help="The CSV input file")
    sp.add_argument(
        "-o", "--output", type=str, default="", help="Output a CSV file with more info."
    )
    sp.add_argument(
        "-b", "--biblio", type=str, default="PARTDI", help="The bibliothèque code"
    )
    sp.set_defaults(func=cli_availabilty_csv)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

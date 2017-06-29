import json
import elasticsearch
import elasticsearch.helpers


def main():
    count = 0
    es = elasticsearch.Elasticsearch()
    docs = elasticsearch.helpers.scan(es, query={"query": {"match_all": {}}}, size=10000)
    with open("documents.json", "wt", encoding="UTF-8") as f:
        for doc in docs:
            if count % 100000 == 0:
                print(".", flush=True, end="")
            json.dump({"index": {"_index": doc["_index"], "_type": doc["_type"]}}, f)
            f.write("\n")
            json.dump(doc["_source"], f)
            f.write("\n")
            count += 1
    print("\nDone")


if __name__ == '__main__':
    main()

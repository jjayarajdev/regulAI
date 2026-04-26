"""All Cypher queries for the GRE — centralized.

Convention: module-level uppercase constants. Parameters are $-prefixed.
Cypher labels and relationship types CANNOT be parameterized in Cypher,
so adapters use Python f-string injection — safe because the values come
from closed `NodeType` / `RelationshipType` enums, never user input.
"""

WIPE_ALL = "MATCH (n:GRENode) DETACH DELETE n"

GET_NODE_BY_ID = "MATCH (n:GRENode {id: $id}) RETURN n"

FIND_BY_NAME_AND_TYPE = """
MATCH (n:GRENode {type: $type, name: $name})
RETURN n
ORDER BY n.version DESC
"""

FIND_LATEST_BY_NAME_AND_TYPE = """
MATCH (n:GRENode {type: $type, name: $name})
WHERE n.status <> 'superseded'
RETURN n
ORDER BY n.version DESC
LIMIT 1
"""

FIND_DOCUMENT_BY_HASH = """
MATCH (d:GRENode:RegulationDocument {hash: $hash})
RETURN d
"""

QUERY_ACTIVE_AS_OF = """
MATCH (n:GRENode {type: $type, name: $name})
WHERE n.status = 'approved'
  AND ($as_of IS NULL OR n.effective_from IS NULL OR n.effective_from <= $as_of)
  AND ($as_of IS NULL OR n.effective_to IS NULL OR n.effective_to > $as_of)
RETURN n
ORDER BY n.version DESC
LIMIT 1
"""

COUNT_NODES = "MATCH (n:GRENode) RETURN count(n) AS count"

COUNT_BY_TYPE = """
MATCH (n:GRENode)
RETURN n.type AS type, count(n) AS count
ORDER BY count DESC
"""

COUNT_RELATIONSHIPS = "MATCH ()-[r]->() RETURN count(r) AS count"

FETCH_SUBGRAPH_BY_DOC = """
MATCH (doc:GRENode:RegulationDocument {id: $document_id})
OPTIONAL MATCH (doc)<-[:CONTAINED_IN]-(rule:Rule)
OPTIONAL MATCH (rule)<-[c:CITES]-(citer:GRENode)
RETURN doc, collect(DISTINCT rule) AS rules, collect(DISTINCT citer) AS citers
"""

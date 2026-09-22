class HybridSearch:

    def __init__(self):
        pass

    def merge(self,vector_results,graph_results,):

        merged = []
        seen = set()

        print("Bat dau ket hop 2 search")
        for node in vector_results:

            node_id = node.node.node_id

            if node_id not in seen:
                merged.append(node)
                seen.add(node_id)

        
        for node in graph_results:

            node_id = node.node.node_id

            if node_id not in seen:
                merged.append(node)
                seen.add(node_id)

        return merged
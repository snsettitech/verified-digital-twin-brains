import uuid
from modules.clients import get_pinecone_index
from modules.embeddings import get_embedding
from modules.observability import supabase
from modules.twin_namespace import get_primary_namespace_for_twin, resolve_creator_id_for_twin

async def inject_verified_memory(escalation_id: str, owner_answer: str):
    """
    Converts an owner's verified answer into a high-priority vector embedding.
    """
    # 1. Fetch escalation and related message to get twin_id
    response = supabase.table("escalations").select("*, messages(conversation_id, conversations(twin_id))").eq("id", escalation_id).single().execute()
    if not response.data:
        raise ValueError(f"Escalation {escalation_id} not found")
    
    twin_id = response.data["messages"]["conversations"]["twin_id"]
    
    # 2. Generate embedding for the owner's answer
    # We embed the answer so it can be retrieved when similar questions are asked
    embedding = get_embedding(owner_answer)
    
    # 3. Upsert to Pinecone with verified metadata
    index = get_pinecone_index()
    vector_id = f"verified_{str(uuid.uuid4())}"
    
    creator_id = resolve_creator_id_for_twin(twin_id)
    namespace = get_primary_namespace_for_twin(twin_id=twin_id, creator_id=creator_id)

    index.upsert(
        vectors=[{
        "id": vector_id,
        "values": embedding,
        "metadata": {
            "text": owner_answer,
            "twin_id": twin_id,
            "creator_id": creator_id,
            "source_id": f"verified_{escalation_id}",
            "is_verified": True,
            "priority": 10 # High priority for verified answers
        }
        }],
        namespace=namespace
    )
    
    return vector_id


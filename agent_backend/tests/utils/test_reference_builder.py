from app.utils.reference_builder import generate_detailed_references, add_inline_citations

def test_generate_detailed_references():
    """
    GIVEN a list of chunks and a generated answer.
    WHEN `generate_detailed_references` is called.
    THEN it should only create references for documents that are actually mentioned in the answer.
    """
    # ARRANGE
    chunks = [
        {'document_name': 'Aegis Policy', 'page': '1'},
        {'document_name': 'BrightShield Policy', 'page': '3'},
        {'document_name': 'Aegis Policy', 'page': '5'}, # Duplicate document
    ]
    # The answer only mentions the Aegis Policy.
    answer = "| Aegis Policy | Covers fire and theft. |"
    
    # ACT
    references, source_mapping = generate_detailed_references(chunks, answer)
    
    # ASSERT
    assert len(references) == 2 # Includes the "-" separator
    assert "Aegis Policy" in references[1]
    # Crucially, BrightShield is NOT in the references.
    assert not any("BrightShield" in ref for ref in references)
    assert source_mapping == {'Aegis Policy': 1}

def test_add_inline_citations():
    """
    GIVEN a generated answer and a source mapping.
    WHEN `add_inline_citations` is called.
    THEN it should correctly insert the citation numbers into the answer text.
    """
    # ARRANGE
    answer = "| Aegis Policy | Covers fire and theft. |\n| BrightShield Policy | Covers liability. |"
    source_mapping = {'Aegis Policy': 1, 'BrightShield Policy': 2}
    
    # ACT
    result = add_inline_citations(answer, [], source_mapping) # The `chunks` argument is not used in this function
    
    # ASSERT
    assert "| Aegis Policy [1] |" in result
    assert "| BrightShield Policy [2] |" in result
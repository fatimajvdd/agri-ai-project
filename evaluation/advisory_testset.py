"""Manually written ground truth for the advisory module.

How the ground truth was established: each SUPPORTED case was written by hand by reading one entry of the
Agricultural Knowledge Base (KB_ID = row number in the CSV, 0-based) and paraphrasing its symptoms in
different words, so the expected answer is the KB entry the paraphrase was written from. BROWSE cases expect
all KB entries of a crop/category. UNSUPPORTED cases are questions that the KB cannot answer (crop absent,
dose/price/weather questions, nonsense); the expected behaviour is a refusal.
"""
SUPPORTED = [  # (question, crop or None, expected KB_ID)
    ("orange powdery stripes along the veins of leaves", "Wheat", 0),
    ("round brown pustules scattered over the leaf", "Wheat", 1),
    ("grains black and powdery with fishy smell", "Wheat", 4),
    ("seedlings cut at the base and termite tunnels", "Wheat", 7),
    ("older leaves pale yellow, plants stunted with few tillers", "Wheat", 10),
    ("plants fall flat after rain or wind", "Wheat", 15),
    ("central shoot dries and white empty panicles", "Rice", 21),
    ("grey centred spindle lesions and the neck turns black", "Rice", 18),
    ("stunted patches with brown rusty spots after transplanting", "Rice", 24),
    ("high water use and a falling water table", "Rice", 27),
    ("leaves curl downward, sticky with sooty mould", "Cotton", 28),
    ("pink larvae inside bolls and rosette flowers", "Cotton", 30),
    ("silvery scratches and leaves cupped upward", "Cotton", 33),
    ("shedding of flowers and young bolls in heat", "Cotton", 35),
    ("split cane shows red tissue and sour smell", "Sugarcane", 39),
    ("black whip-like structure emerging from the top", "Sugarcane", 40),
    ("ragged holes in whorl leaves with sawdust-like frass", "Maize", 45),
    ("yellow V-shaped area starting at the leaf tip", "Maize", 49),
    ("water-soaked patches with white mould in humid mornings", "Potato", 51),
    ("blackened leaves after clear cold nights", "Potato", 54),
    ("white powdery coating on flowers and fruit drop", "Mango", 63),
    ("puncture marks on ripening fruit with maggots", "Mango", 66),
    ("holes in pods with larvae feeding on seeds", "Gram", 71),
    ("dark sunken leathery patch at the blossom end of fruit", "Tomato", 78),
    ("white crust on the soil surface and leaf tip burn", None, 115),
    ("swarms of insects eating all green parts", None, 123),
    ("serpentine silvery mines in young leaves", "Kinno", 59),
    ("yellow mosaic patches on leaves and few small pods", "Mong", 83),
]
BROWSE = [  # (question, crop, category, expected KB_IDs that must all be returned)
    ("What are common diseases affecting rice?", "Rice", "Disease", {17, 18, 19, 20}),
    ("common pest problems in cotton", "Cotton", "Pest", {28, 30, 31, 32, 33, 34}),
    ("What are common pest problems in maize?", "Maize", "Pest", {45, 46}),
    ("diseases of wheat", "Wheat", "Disease", {0, 1, 2, 3, 4, 5}),
]
UNSUPPORTED = [  # (question, crop)
    ("brown spots on leaves", "Apple"),
    ("What is the market price of wheat per maund?", None),
    ("how much urea per acre for rice", "Rice"),
    ("Will it rain tomorrow in Lahore?", None),
    ("tell me a joke", None),
    ("engine overheating", "Wheat"),
    ("pods bursting with spiders", "Sesamum"),
    ("how to apply for a tractor loan", "Cotton"),
    ("yellow leaves", "Banana"),
    ("pesticide dosage for cotton whitefly", "Cotton"),
]

# Farmer-style stress set: everyday wording that often does NOT share vocabulary with the KB.
# (question, crop, set of acceptable KB_IDs). A case passes if an acceptable entry is in the top 3.
HARD = [
    ("my wheat crop has yellow leaves", "Wheat", {0, 1, 10}),
    ("cotton plants dropping their bolls", "Cotton", {35, 37}),
    ("rice plants turning yellow and drying in patches", "Rice", {23}),
    ("worms eating my maize leaves", "Maize", {45, 46}),
    ("my tomatoes have rotten bottoms", "Tomato", {78}),
    ("potato leaves have dark spots with rings", "Potato", {52}),
    ("mango flowers falling off with white dust", "Mango", {63, 67}),
    ("sugarcane stalks are hollow and bad smell", "Sugarcane", {39, 41}),
    ("wheat plants are very short with thin stems", "Wheat", {10, 11, 12}),
    ("crop is dying after flood water stood in field", None, {117}),
]

# API_KEY = 'nk-3d_JPRP2c1FKxVTqIbpoATrtTvWQBDBk8ZR44am-YLU'


# import torch.nn.functional as F
# from transformers import AutoTokenizer, AutoModel, AutoImageProcessor
# from PIL import Image
# import requests

# processor = AutoImageProcessor.from_pretrained("nomic-ai/nomic-embed-vision-v1.5")
# vision_model = AutoModel.from_pretrained("nomic-ai/nomic-embed-vision-v1.5", trust_remote_code=True)

# image = Image.open('Saved/253c486.jpg')

# inputs = processor(image, return_tensors="pt")

# img_emb = vision_model(**inputs).last_hidden_state
# img_embeddings = F.normalize(img_emb[:, 0], p=2, dim=1)


from nomic import atlas
import numpy as np

num_embeddings = 10000
embeddings = np.random.rand(num_embeddings, 512)

dataset = atlas.map_data(embeddings=embeddings)
print(dataset)
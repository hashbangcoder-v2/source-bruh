Source Bruh 

Source-Bruh is a lightweight android app that allows uers to eaily semantic-search through saved images from various android apps (particularly twitter/X) using the share-button along with meta-data of the image. For example, a user finds a particular infographic on twitter that describes the GDP growth of OECD countries after Covid-19. 
- User clicks share button on the twitter app and selects Source-Bruh from the list of apps to share to
- Source-Bruh receives the image and meta-data (e.g. title, description, tags) from the twitter app
- Source-Bruh uses an LLM / embedding model to generate a vector representation of the image and geenrate a detailed description of the image (e.g. "This infographic shows the GDP growth of OECD countries after Covid-19, with a bar chart comparing the growth rates of different countries.")
- Source-Bruh saves the image, meta-data, vector representation, and description in a local database (e.g. SQLite) on the user's device
- User can later search for the image using natural language queries (e.g. "growth OECD post-2020") and Source-Bruh retrieves the relevant images based on the vector similarity and displays them to the user.

These are the main features of the app:

- Login Page

When no user is logged-in, it will display a login page with a background image (@C:\Users\vigne\projects\source-bruh\frontend\public\icons\icon.png) and `Login With Google` button. The app needs access to basic user information (name, email) and read-access to user google-photos. When a user is logged-in, it will automatically load the Query page

- Settings page 
Accessible through Settings icon in the Login that will open The following settings have to be configured
  - API key : Text field for an API key that with an edit option. It will be masked for security reasons
    - in the future, we will add a local LLM option instead of an API key
  - user info (read-only) that displays the logged-in user's name and email

- Query Page : Text input field with a query icon. title text - "Need a source?". Settings icon in top right and will navigate to the Settings page. 
  - When a user enters a query and clicks the query icon, it will send the query to the backend API and retrieve relevant image results based on vector similarity search. The results will be displayed in a grid format with 3 images per row. Each image result will display the image, title, and description. Users can click on an image result to view it in full screen along with its meta-data (title, description, tags).
  - Scrolling down the results page will trigger pagination and load more results if available. If no results are found, it will display a message indicating that no relevant images were found for the query.
  - While image is loading it will display a blurred image placeholder. Add a timeout of 5 seconds for loading the image, after which it will display a default "image not available" placeholder if the image fails to load.


Add the app to Android sharesheet. When i try to share a new image (from another app or from device), Source-Bruh should show up as an option. Selecting this will add a new image to be indexed by the backend. The app will receive the image and its meta-data (e.g. title, description, tags) from the sharing app, generate a vector representation and detailed description using an LLM/embedding model, and save all this information in a local database (e.g. SQLite) on the user's device. The app will then upload this data to the backend for indexing and retrieval during search queries.
- Add instrunctions on how to locally run the app on an Android device, including setting up the development environment, connecting the device, and running the app. Include troubleshooting tips for common issues that may arise during development and testing

- Backend 
  - Backend is Firebase with Firestore and Functions to store image data and execute logic . Check @C:\Users\vigne\projects\source-bruh\functions for more details on the backend implementation
  - Add detailed instructions on how to set up the Firebase backend, including creating a Firestore database, setting up authentication, and deploying cloud functions. Include code snippets for the cloud functions that handle image data processing and indexing



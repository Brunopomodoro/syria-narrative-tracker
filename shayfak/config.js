// Shayfak site settings. Everything here is public by design (a Firebase web config is not a secret;
// the security lives in database.rules.json, App Check and the Cloud Functions).
window.SHAYFAK = {
  firebase: {
    apiKey:            "AIzaSyCwAB5zJmR_SEaWzGXrtyLS557Bl6fqy10",
    authDomain:        "shayfak-d7a08.firebaseapp.com",
    databaseURL:       "https://shayfak-d7a08-default-rtdb.europe-west1.firebasedatabase.app",
    projectId:         "shayfak-d7a08",
    storageBucket:     "shayfak-d7a08.firebasestorage.app",
    messagingSenderId: "695892583415",
    appId:             "1:695892583415:web:a4678ea232b6921d7b44f2"
  },
  // Region the Cloud Functions are deployed in (see firebase/functions/index.js).
  functionsRegion: "europe-west1",
  // reCAPTCHA v3 site key for Firebase App Check. Leave empty only while testing with ENFORCE_APP_CHECK=false.
  appCheckSiteKey: "",
  // Below this many votes in a month, no percentage is shown. Keep equal to config.yaml min_sample.
  minSample: 30,
  // Public site URL; share links point at p/<slug>.html there (those pages carry the preview image).
  siteUrl: "https://shayfak.org",
  // Where the data lives relative to this page.
  dataPath: "data/"
};

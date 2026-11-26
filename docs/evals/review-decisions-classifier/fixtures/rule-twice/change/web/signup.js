// Signup form: posts to /signup.
const form = document.querySelector("#signup");

// Mirrors username_error in server/validate.py.
const USERNAME_MAX = 30;
const USERNAME_PATTERN = /^[a-z0-9_]+$/;

function usernameError(username) {
  if (username.length > USERNAME_MAX) return "too long";
  if (!USERNAME_PATTERN.test(username)) return "only lowercase letters, digits and _";
  return null;
}

form.addEventListener("submit", (event) => {
  const error = usernameError(form.elements.username.value);
  if (error) {
    event.preventDefault();
    form.querySelector(".error").textContent = error;
  }
  // The server answers 400 with the error text when a field is invalid.
});

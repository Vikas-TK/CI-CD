// Client-side form validation for Registration and Login
document.addEventListener("DOMContentLoaded", () => {
    const registerForm = document.getElementById("patientRegisterForm");
    
    if (registerForm) {
        const passwordInput = document.getElementById("password");
        const confirmPasswordInput = document.getElementById("confirm_password");
        const passwordMatchFeedback = document.getElementById("passwordMatchFeedback");

        function checkPasswordMatch() {
            if (!confirmPasswordInput || !passwordInput) return;
            
            if (confirmPasswordInput.value === "") {
                confirmPasswordInput.classList.remove("is-valid", "is-invalid");
                if (passwordMatchFeedback) passwordMatchFeedback.textContent = "";
                return;
            }

            if (passwordInput.value === confirmPasswordInput.value) {
                confirmPasswordInput.classList.remove("is-invalid");
                confirmPasswordInput.classList.add("is-valid");
                if (passwordMatchFeedback) {
                    passwordMatchFeedback.textContent = "Passwords match.";
                    passwordMatchFeedback.className = "valid-feedback d-block";
                }
            } else {
                confirmPasswordInput.classList.remove("is-valid");
                confirmPasswordInput.classList.add("is-invalid");
                if (passwordMatchFeedback) {
                    passwordMatchFeedback.textContent = "Passwords do not match.";
                    passwordMatchFeedback.className = "invalid-feedback d-block";
                }
            }
        }

        if (passwordInput && confirmPasswordInput) {
            passwordInput.addEventListener("input", checkPasswordMatch);
            confirmPasswordInput.addEventListener("input", checkPasswordMatch);
        }

        registerForm.addEventListener("submit", (e) => {
            if (passwordInput.value !== confirmPasswordInput.value) {
                e.preventDefault();
                checkPasswordMatch();
                confirmPasswordInput.focus();
            }
        });
    }
});

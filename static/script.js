document.addEventListener("DOMContentLoaded", function () {
  // Select all editable cells
  document.querySelectorAll(".editable").forEach(cell => {
      cell.addEventListener("click", function () {
          // If the cell is empty, add an input field
          if (!this.querySelector("input")) {
            let input = document.createElement("input");
            input.type = "text";
            input.value = this.textContent.trim(); // Set the initial value as empty
            input.dataset.name = this.dataset.name; // Store the 'name' attribute value

            this.innerHTML = ""; // Clear the cell content
            this.appendChild(input); // Insert the input inside the cell

            input.focus(); // Focus on the input field so the user can start typing

            // When the input loses focus (blur event),or Enter pressed save the entered value
            
            input.addEventListener("blur", saveInput);
            input.addEventListener("keypress", function (event) {
              if (event.key == "Enter") {
                saveInput()
              }
            });

            function saveInput () {
              let newValue = input.value.trim();
              input.parentElement.innerHTML = newValue; // Replace input with new value
            }
          }
      });
  });
});

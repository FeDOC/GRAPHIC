// Get people list from HTML
const people = JSON.parse(document.getElementById('people-data').dataset.people);

// Global suggestions container
const suggestionBox = document.createElement("div");
suggestionBox.classList.add("autocomplete-suggestions");
document.body.appendChild(suggestionBox);

document.addEventListener("DOMContentLoaded", function () {
    // Select all editable cells
    document.querySelectorAll(".editable").forEach(cell => {
        cell.addEventListener("click", function () {
            // If the cell is empty, add an input field
            if (!this.querySelector("input")) {
                const td = this;
                let input = document.createElement("input");
                input.type = "text";
                input.value = td.textContent.trim(); 
                input.dataset.name = td.dataset.name; 
                
                td.innerHTML = "";
                td.appendChild(input);
                input.focus();
                
                input.addEventListener("input", function () {
                    const value = this.value.toLowerCase();
                    suggestionBox.innerHTML = "";

                    if (!value) {
                        suggestionBox.style.display = "none";
                        return;
                    }

                    const matches = people.filter(name => name.toLowerCase().includes(value));
                    matches.forEach(match => {
                        let option = document.createElement("div");
                        option.classList.add("autocomplete-option");
                        option.textContent = match;

                        option.addEventListener("mousedown", function () {
                            input.value = match;
                            td.innerHTML = match;  // Save to table cell (td)
                            suggestionBox.style.display = "none";
                        });

                        suggestionBox.appendChild(option);
                    });

                    const rect = input.getBoundingClientRect();
                    suggestionBox.style.top = rect.bottom + window.scrollY + "px";
                    suggestionBox.style.left = rect.left + window.scrollX + "px";
                    suggestionBox.style.width = rect.width + "px";
                    suggestionBox.style.display = "block";
                
                });

                function saveInput() {
                    td.innerHTML = input.value.trim();
                    suggestionBox.style.display = "none";
                }

                input.addEventListener("blur", function () {
                    setTimeout(saveInput, 100);
                });

                input.addEventListener("keypress", function (event) {
                    if (event.key === "Enter") saveInput();
                });
            }
        });
    });
});

document.getElementById('save-form')?.addEventListener('submit', function() {
    document.querySelectorAll('.editable').forEach(td => {
        const hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = td.dataset.name;       // e.g., "name_OTVET_1"
        hidden.value = td.textContent.trim();
        this.appendChild(hidden);
    });
})
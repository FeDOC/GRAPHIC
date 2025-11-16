const page = document.body.id //get body id (to run js parts for specific page)

// INDEX PAGE 
if (page === 'index-page') {

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

    // Hidden input for each table cell to save filled names  
    document.getElementById('save-form')?.addEventListener('submit', function() {
        document.querySelectorAll('.editable').forEach(td => {
            const hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = td.dataset.name;       // e.g., "name_OTVET_1"
            hidden.value = td.textContent.trim();
            this.appendChild(hidden);
        });
    });
}

// ACCOUNT PAGE 
if (page === 'account-page') {
    // Interactive tabs 
    const tabs = document.querySelectorAll('.tab');
    const contents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(tab.dataset.tab).classList.add('active');
        });
    });

    // Add person logic
    const addBtn = document.getElementById('add-person-btn');
    const tableBody = document.querySelector('#people-table tbody');

    addBtn.addEventListener('click', () => {
        // Create new row
        const row = document.createElement('tr');

        // Action buttons
        const actionTd = document.createElement('td');
        const applyBtn = document.createElement('button');
        applyBtn.textContent = 'Apply'
        applyBtn.classList.add('action-btn', 'apply')

        const deleteBtn = document.createElement('button');
        deleteBtn.textContent = 'Delete'
        deleteBtn.classList.add('action-btn', 'delete')

        actionTd.appendChild(applyBtn);
        actionTd.appendChild(deleteBtn);
        row.appendChild(actionTd);

        // Name input
        const nameTd = document.createElement('td');
        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.placeholder = 'Name';
        nameInput.required = true;
        nameTd.appendChild(nameInput);
        row.appendChild(nameTd);

        // Exception dates (list)
        const exceptionTd = document.createElement('td');
        const exceptionInput = document.createElement('input');
        exceptionInput.type = 'text';
        exceptionInput.placeholder = 'Day, day, ...';
        exceptionInput.required = true;
        exceptionTd.appendChild(exceptionInput);
        row.appendChild(exceptionTd);

        // Number of shifts
        const shiftsTd = document.createElement('td'); 
        shiftsTd.style.width = '8%';
        const shiftsInput = document.createElement('input');
        shiftsInput.type = 'number';
        shiftsInput.min = 0;
        shiftsInput.value = 0;
        shiftsInput.required = true;
        shiftsInput.style.width = '50%';
        shiftsInput.style.boxSizing = 'border-box';
        shiftsTd.appendChild(shiftsInput);
        row.appendChild(shiftsTd);

        // Place (multi-select)
        const placeTd = document.createElement('td');
        placeTd.style.width = '40%';
        const container = document.createElement('div'); // Container for checkboxes
        container.style.display = "flex";
        container.style.gap = "10px";
        container.style.alignItems = 'center';
        container.style.justifyContent = 'center';
        ['OTV','DIAGN','EXTR','PLAN','GREEN','YELLOW', 'TORAC'].forEach(letter => {
            const item = document.createElement('div');
            item.style.display = 'flex';
            item.style.flexDirection = "column";
            item.style.alignItems = "center";

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = letter;
            checkbox.id = `chk-${letter}`;

            const label = document.createElement('label');
            label.htmlFor = checkbox.id;
            label.textContent = letter;

            item.appendChild(checkbox);
            item.appendChild(label);

            container.appendChild(item);
        }); // Containers with checkbox for each ZONE 
        placeTd.appendChild(container);
        row.appendChild(placeTd);

        // Append row to table
        tableBody.appendChild(row);


        // Apply button -> freeze row
        applyBtn.addEventListener('click', () => {
            const name = nameInput.value.trim();
            const exception = exceptionInput.value.trim();
            const shifts = shiftsInput.value;
            const places = Array.from(container.querySelectorAll('input[type="checkbox"]:checked'))
                                .map(checkbox => checkbox.value);

            if (places.length === 0) {
            alert("Please select at least one place.");
            return;
            }

            if (!name || !exception || !shifts) {
                alert("Please fill all required fields to fill person in table.");
                return;
            }

            console.log({ name, exception, shifts, places });

            nameTd.textContent = name;
            exceptionTd.textContent = exception;
            shiftsTd.textContent = shifts;
            placeTd.textContent = places.join(', ');

            applyBtn.remove();
        });

        // Delete button → remove row
        deleteBtn.addEventListener('click', () => {
            row.remove();
        });
    });
};
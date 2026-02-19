const page = document.body.id //get body id (to run js parts for specific page)

// ----------------------------
// ACCOUNT PAGE 
// ----------------------------

if (page === 'account-page') {

    // ---------------------------- 
    // PAGE HAS TABS:
    // 1. WORKERS 
    // 1.1 Has table with workers name, role, vacations dates and place. Can add, edit and delete workers)
    //
    // 2. MONTHS (has table with workers name, role, number of shifts in month, 
    // exception dates and place) 
    // ----------------------------

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

    // ----------------------------
    // PEOPLE TAB
    // ----------------------------

    const addBtn = document.getElementById('add-person-btn');
    const tableBody = document.querySelector('#workers-table tbody');

    // Add worker button
    addBtn.addEventListener('click', () => {
        // Create new row
        const row = document.createElement('tr');

        // Action buttons
        const actionTd = document.createElement('td');
        actionTd.style.width = '7%'
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
        nameTd.appendChild(nameInput);
        row.appendChild(nameTd);

        // Role input
        const roleTd = document.createElement('td');
        const container_radio = document.createElement('div');
        container_radio.style.display = "flex";
        container_radio.style.gap = "10px";
        container_radio.style.alignItems = 'center';
        container_radio.style.justifyContent = 'center';
        const roleName = `role-${Date.now()}`;
        ['Day', 'Shifter'].forEach(role => {
            const item = document.createElement('div');
            item.style.display = 'flex';
            item.style.flexDirection = "column";
            item.style.alignItems = "center";

            const radio = document.createElement('input');
            radio.type = 'radio';
            radio.value = role;
            radio.name = roleName;
            radio.id = `rad-${role}-${Date.now()}`;

            // For shifter make 8 as number of shifts 
            radio.addEventListener('change', () => {
                if (radio.value === 'Shifter') {
                    shiftsInput.value = 8;
                } else {
                    shiftsInput.value = 0; // 
                }
            });

            const label = document.createElement('label');
            label.htmlFor = radio.id;
            label.textContent = role;

            item.appendChild(radio);
            item.appendChild(label);

            container_radio.appendChild(item)
        });
        roleTd.appendChild(container_radio);
        row.appendChild(roleTd);
        
        // Vacations dates
        const vacationTd = document.createElement('td');
        vacationTd.style.width = '20%'
        const vacationInput = document.createElement('textarea');
        vacationInput.style.minHeight = '30px';
        vacationInput.style.width = '100%';
        vacationInput.style.boxSizing = 'border-box';
        vacationInput.placeholder = 'DD.MM.YY - DD.MM.YY, ...';
        vacationInput.addEventListener('input', () => {
            vacationInput.style.height = 'auto';
            vacationInput.style.height = vacationInput.scrollHeight + 'px';
        });
        vacationTd.appendChild(vacationInput);
        vacationInput.dispatchEvent(new Event('input'));
        row.appendChild(vacationTd);

        // Number of shifts
        const shiftsTd = document.createElement('td'); 
        const shiftsInput = document.createElement('input');
        shiftsInput.type = 'number';
        shiftsInput.min = 0;
        shiftsInput.value = 0;
        shiftsInput.style.width = '60%';
        //shiftsInput.style.boxSizing = 'border-box';
        shiftsTd.appendChild(shiftsInput);
        row.appendChild(shiftsTd);

        // Place (multi-select)
        const placeTd = document.createElement('td');
        placeTd.style.width = '40%';
        const container_checkbox = document.createElement('div'); // Container for checkboxes
        container_checkbox.style.display = "flex";
        container_checkbox.style.gap = "10px";
        container_checkbox.style.alignItems = 'center';
        container_checkbox.style.justifyContent = 'center';
        ['OTVET','DIAGN','EXTR','PLAN','GREEN','YELLOW', 'TORAC'].forEach(zone => {
            const item = document.createElement('div');
            item.style.display = 'flex';
            item.style.flexDirection = "column";
            item.style.alignItems = "center";

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = zone;
            checkbox.id = `chk-${zone}`;

            const label = document.createElement('label');
            label.htmlFor = checkbox.id;
            label.textContent = zone;

            item.appendChild(checkbox);
            item.appendChild(label);

            container_checkbox.appendChild(item);
        }); // Containers with checkbox for each ZONE 

        placeTd.appendChild(container_checkbox);
        row.appendChild(placeTd);

        // Append row to table
        tableBody.appendChild(row);

        // Apply button -> freeze row -> send info to SQL workers
        applyBtn.addEventListener('click', () => {
            const name = nameInput.value.trim();
            const role = container_radio.querySelector('input:checked')?.value || null;
            const vacations = vacationInput.value.split(',').map(x => x.trim())
            const shifts = shiftsInput.value;
            const places = Array.from(container_checkbox.querySelectorAll('input[type="checkbox"]:checked'))
                                .map(checkbox => checkbox.value);

            if (places.length === 0) {
                alert("Please select at least one place");
                return;
            }

            if (!name || !role || !shifts) {
                alert("Please fill all required fields to fill person in table");
                return;
            }

            nameTd.textContent = name;
            roleTd.textContent = role;
            vacationTd.textContent = vacations.join(', ');
            shiftsTd.textContent = shifts;
            placeTd.textContent = places.join(', ');

            applyBtn.remove();
            deleteBtn.remove();
            WorkersEditableCells(row);

            fetch('/account/workers/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, role, shifts, places, vacations })
            })
            .then(res =>
                res.json().then(body => ({ res, body }))
            )
            .then(({ res, body }) => {
                if (!res.ok || body.ok === false) {
                    alert(body.error || "Server error");
                    deleteBtn.click();
                    return;
                }
                console.log(body.data);
            });
        });

        // Delete button → remove row
        deleteBtn.addEventListener('click', () => {
            row.remove();
        });
    });

    // Make table cells editable
    function WorkersEditableCells(row) {
        const cells = row.querySelectorAll('td'); // choose all td in row
        
        const actionCell = cells[0];

        let editBtn = actionCell.querySelector('button.edit');
        if (!editBtn) {
            editBtn = document.createElement('button');
            editBtn.textContent = 'Edit';
            editBtn.classList.add('action-btn', 'edit');
            actionCell.appendChild(editBtn);
        }

        let deleteBtn = actionCell.querySelector('button.delete');
        if (!deleteBtn) {
            deleteBtn = document.createElement('button');
            deleteBtn.textContent = 'Delete';
            deleteBtn.classList.add('action-btn', 'delete');
            actionCell.appendChild(deleteBtn);
        }

        // Edit button logic
        editBtn.addEventListener('click', () => {
            if (editBtn.textContent === 'Edit') {
                enterEditMode(row, editBtn, deleteBtn);
            } else if (editBtn.textContent === 'Apply') {
                applyRowChanges(row, editBtn, deleteBtn);
            }
        });

        // Delete button logic
        deleteBtn.addEventListener('click', () => {
            const name = cells[1].textContent; // assume name is unique identifier
            if (!confirm(`Are you sure you want to delete ${name}?`)) return;

            // Send delete request to sql workers
            fetch('/account/workers/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    row.remove();
                } else {
                    alert("Failed to delete row: " + data.error)
                }
            });
        });
    }
    // Each row has EditableCells
    document.querySelectorAll('#workers-table tbody tr').forEach(WorkersEditableCells);

    // Edit cells in row 
    function enterEditMode(row, editBtn, deleteBtn) {
        const cells = row.querySelectorAll('td');
        
        // Action cell
        cells[0].style.width = '7%'
        editBtn.textContent = 'Apply';
        // Remove delete button when edit
        deleteBtn.style.display = 'none';

        // Name cell
        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.value = cells[1].textContent;
        cells[1].textContent = '';
        cells[1].appendChild(nameInput);

        // Role cell
        const roleContainer = document.createElement('div');
        roleContainer.style.display = 'flex';
        roleContainer.style.gap = '10px';
        roleContainer.style.alignItems = 'center';
        roleContainer.style.justifyContent = 'center';
        const roleName = `role-edit-${Date.now()}`;
        ['Day', 'Shifter'].forEach(role => {
            const radio = document.createElement('input');
            radio.type = 'radio';
            radio.name = roleName;
            radio.value = role;
            radio.checked = cells[2].textContent === role;
            const label = document.createElement('label');
            label.textContent = role;
            const wrapper = document.createElement('div');
            wrapper.style.textAlign = 'center';
            wrapper.appendChild(radio);
            wrapper.appendChild(label);
            roleContainer.appendChild(wrapper);

            radio.addEventListener('change', () => {
                // auto update number of shifts
                const shiftsInput = cells[4].querySelector('input');
                if (role === 'Shifter') {
                    shiftsInput.value = 8;
                } else {
                    shiftsInput.value = 0;
                };
            });
        });
        cells[2].textContent = '';
        cells[2].appendChild(roleContainer);

        // Vacations cell 
        const vacInput = document.createElement('textarea');
        vacInput.value = cells[3].textContent;
        cells[3].textContent = '';
        cells[3].style.width = '20%';
        vacInput.style.width = '100%';
        vacInput.style.boxSizing = 'border-box';
        vacInput.style.overflow = 'hidden';
        vacInput.addEventListener('input', () => {
            vacInput.style.height = 'auto';
            vacInput.style.height = vacInput.scrollHeight + 'px';
        });
        cells[3].appendChild(vacInput);
        vacInput.dispatchEvent(new Event('input'));

        // Number of shifts cell
        const shiftsInput = document.createElement('input');
        shiftsInput.type = 'number';
        shiftsInput.min = 0;
        shiftsInput.style.width = '50%';
        shiftsInput.value = parseInt(cells[4].textContent) || 0;
        cells[4].style.width = '8%';
        cells[4].textContent = '';
        cells[4].appendChild(shiftsInput);

        // Places
        const placeContainer = document.createElement('div');
        placeContainer.style.display = 'flex';
        placeContainer.style.gap = '10px';
        const originalPlaces = cells[5].textContent.split(',').map(x => x.trim());
        ['OTVET','DIAGN','EXTR','PLAN','GREEN','YELLOW','TORAC'].forEach(zone => {
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = zone;
            checkbox.checked = originalPlaces.includes(zone);
            const label = document.createElement('label');
            label.textContent = zone;
            const wrapper = document.createElement('div');
            wrapper.style.textAlign = 'center';
            wrapper.appendChild(checkbox);
            wrapper.appendChild(label);
            placeContainer.appendChild(wrapper);
        });
        cells[5].textContent = '';
        cells[5].style.width = '40%'
        cells[5].appendChild(placeContainer);
    }

    // Apply changes in row
    function applyRowChanges(row, editBtn, deleteBtn) {
        const cells = row.querySelectorAll('td');

        const name = cells[1].querySelector('input').value.trim();
        const role = cells[2].querySelector('input:checked')?.value || '';
        const vacations = cells[3].querySelector('textarea').value.split(',').map(x => x.trim());
        const shifts = parseInt(cells[4].querySelector('input').value) || 0;
        const places = Array.from(cells[5].querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.value);

        if (!name || !role || places.length === 0) {
            alert('Please fill all required fields and select at least one place');
            return;
        }

        // Replace inputs with text
        cells[1].textContent = name;
        cells[2].textContent = role;
        cells[3].textContent = vacations.join(', ');
        cells[4].textContent = shifts;
        cells[5].textContent = places.join(', ');

        editBtn.textContent = 'Edit';
        deleteBtn.style.display = 'inline-block';

        // Send updated row to backend
        fetch('/account/workers/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, role, vacations, shifts, places })
        })
        .then(res => {
            if (!res.ok) {
                return res.text().then(msg => {
                    throw new Error(msg);
                }) 
            }
        }) 
        .catch(err => {
            alert(err.message)
        });
    }

    // ----------------------------
    // MONTHS TAB
    // ----------------------------

    const monthsTabs = document.querySelectorAll('.month-tab');
    const monthContents = document.querySelectorAll('.month-tab-content');

    // Previous-Current-Next month tab switching
    monthsTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // first inactivate all tabs and contents 
            monthsTabs.forEach(t => t.classList.remove('active'));
            monthContents.forEach(c => c.classList.remove('active'));
            // activate clicked one tab + content
            tab.classList.add('active');
            document.getElementById(tab.dataset.tab).classList.add('active');
        });
    });


    // ----------------------------
    // MONTH WORKERS TABLE
    // ----------------------------

        // ----------------------------
        // EDIT ROWS 
        // ----------------------------

    function MonthEditableCells(row) {
        const cells = row.querySelectorAll('td'); // choose all td in row
        const actionCell = cells[0]; // choose action cell

        let editBtn = actionCell.querySelector('.edit-btn'); // choose Edit button

        // Edit button logic
        editBtn.addEventListener('click', () => {
            if (editBtn.textContent === 'Edit') {
                editMonthRow(row, editBtn);
            } else if (editBtn.textContent === 'Apply') {
                applyMonthRow(row, editBtn);
            }
        });
    }

    function editMonthRow(row, editBtn) {
        const cells = row.querySelectorAll('td');

        // Action cell
        cells[0].style.width = '15%'
        editBtn.textContent = 'Apply';

        // Exceptions Dates cell 
        const excInput = document.createElement('textarea');
        excInput.style.width = '100%';
        excInput.style.font = 'inherit';
        excInput.style.paddingBottom = '5px';
        excInput.rows = excInput.value.split('\n').length;
        excInput.style.boxSizing = 'border-box';
        excInput.style.display = 'block';
        excInput.value = cells[2].textContent;
        excInput.addEventListener('input', () => { // resizing if add new lines
            excInput.style.height = 'auto';
            excInput.style.height = excInput.scrollHeight + 'px';
        });
        cells[2].dataset.oldValue = cells[2].textContent; // save old text to compare in apply 
        cells[2].textContent = '';
        cells[2].style.padding = '1px';
        cells[2].style.width = '40%'
        cells[2].appendChild(excInput);
        excInput.dispatchEvent(new Event('input'));

        // Shifts number cell
        const shiftsInput = document.createElement('input');
        shiftsInput.type = 'number';
        shiftsInput.min = 0;
        shiftsInput.style.width = '40%';
        shiftsInput.value = parseInt(cells[3].textContent);
        cells[3].style.width = '8%';
        cells[3].dataset.oldValue = cells[3].textContent;
        cells[3].textContent = '';
        cells[3].appendChild(shiftsInput);
    }

    function applyMonthRow(row, editBtn) {
        const cells = row.querySelectorAll('td');
        
        // Prev numbers
        const oldExceptions = cells[2].dataset.oldValue
            ? cells[2].dataset.oldValue.split(',').map(x => x.trim()) // if exist
            : []; // if not exist
        const oldShifts = cells[3].dataset.oldValue 
            ? cells[3].dataset.oldValue
            : '';

        // New input
        const newExceptions = cells[2].querySelector('textarea').value.split(',').map(x => x.trim());
        const newShifts = cells[3].querySelector('input').value || '';

        // Exceptions
        cells[2].textContent = '';
        newExceptions.forEach((exc, i) => {
            const span = document.createElement('span');
            span.textContent = exc;
            // Compare with old: if it’s new, make green
            if (!oldExceptions.includes(exc)) {
                span.style.color = 'green';
            }
            cells[2].appendChild(span);
            if (i < newExceptions.length - 1) {
                cells[2].appendChild(document.createTextNode(', '));
            }
        });

        // Shifts
        cells[3].textContent = '';
        const shiftSpan = document.createElement('span');
        shiftSpan.textContent = newShifts;
        if (oldShifts !== newShifts) {
            shiftSpan.style.color = 'green';
        }
        cells[3].appendChild(shiftSpan);

        editBtn.textContent = 'Edit';
    }

        // ----------------------------
        // COLLECT INFO
        // ----------------------------

    // Collects exceptions and shifts from cur month
    function exceptionsShifts() {
        const table = document.querySelector('.month-workers-table.cur');
        const rows = table.tBodies[0].rows; // skip header
        const result = {}
        Array.from(rows).forEach(row => {
            const cells = row.cells;
            const name = cells[1].innerText.trim();
            const exceptions = cells[2].innerText.trim();
            const shifts = parseInt(cells[3].innerText.trim(), 10);
            result[name] = {exceptions: exceptions, 
                            shifts: shifts
            }
        });
        return result
    }

    // ----------------------------
    // SHIFTS TABLE
    // ----------------------------

    // Collects inputs in shifts table (booked days) 
    function collectEditedCells(form) {
        form.querySelectorAll('input[type="hidden"]').forEach(i => i.remove());
        const editedTds = [];
        document.querySelectorAll('.cur-editable').forEach(td => {
            const value = td.textContent.trim();
            if (value !== "") {
                const hidden = document.createElement('input');
                hidden.type = 'hidden';
                hidden.name = td.dataset.name;
                hidden.value = value;
                form.appendChild(hidden);
                editedTds.push(td);
            }
        });
        return editedTds;
    }

    // Removes generated shifts from shifts table, only booked stay 
    function clearGenerated() {
        const activeTab = document.querySelector('.month-tab-content.active');
        const tbody = activeTab.querySelector('.month-shifts-table tbody');
        Array.from(tbody.rows).forEach(row => {
            // skip first column (day)
            Array.from(row.cells).slice(1).forEach(td => {
                if (!td.classList.contains('booked')) {
                    td.textContent = '';
                }
            });
        });
    }

    // Fill shifts table with generated graphic data
    function fillTable(graphic, booked) {
        const activeTab = document.querySelector('.month-tab-content.active');
        const table = activeTab.querySelector('.month-shifts-table');
        const tbody = table.querySelector('tbody');
        const headerCells = table.querySelectorAll('thead th');
        const zones = Array.from(headerCells)
                            .slice(1) // skip first column (Day)
                            .map(th => th.textContent.trim());
        Array.from(tbody.rows).forEach(row => {
            Array.from(row.cells).slice(1).forEach(td => td.textContent = '');
        });

        Object.keys(graphic)
            .sort((a, b) => Number(a) - Number(b)) // days as numbers
            .forEach((day, rowIndex) => {
                const tr = tbody.rows[rowIndex]
                zones.forEach((zone, colIndex) => {
                    const td = tr.cells[colIndex + 1]; 
                    td.textContent = graphic[day][zone] ?? '';
                });    
            });
    }

    // Clear all shifts table cells 
    function clearAll() {
        const activeTab = document.querySelector('.month-tab-content.active');
        const tbody = activeTab.querySelector('.month-shifts-table tbody');
        Array.from(tbody.rows).forEach(row => {
            // skip first column (day)
            Array.from(row.cells).slice(1).forEach(td => {
                td.textContent = '';
                td.classList.remove('booked')
            });
        });
    }

    // ----------------------------
    // MAIN DOM LISTENER
    // ----------------------------

    document.addEventListener("DOMContentLoaded", async () => {

        // async function to load workers names from SQL(workers)
        const data = await (await fetch("/api/names")).json();
        const names = data.names ?? [];

        // Global suggestions container
        const suggestionBox = document.createElement("div");
        suggestionBox.classList.add("autocomplete-suggestions");
        document.body.appendChild(suggestionBox);

        // Apply editable rows function to cur month workers table
        document.querySelectorAll('.month-workers-table.cur tbody tr').forEach(MonthEditableCells);
        
        // Save exceptions and shifts for cur month
        document.getElementById('cur-workers-save-form')?.addEventListener('submit', function(e) {
            e.preventDefault();
            fetch('/account/months/save_cur', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(exceptionsShifts())
            });
        });

        // Edit each td in cur month shifts table
        document.querySelectorAll(".cur-editable").forEach(cell => {
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

                        const matches = names.filter(name => name.toLowerCase().includes(value));
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

        // Hidden input for each table cell to save filled names  
        document.getElementById('cur-save-form')?.addEventListener('submit', function(e) {
            e.preventDefault();
            const editedTds = collectEditedCells(this);
            if (editedTds.length === 0) {
                return; // nothing to save
            }
            // otherwise collect form data
            else {
                fetch('/account/shifts/save_cur', {
                    method: "POST",
                    body: new FormData(this)
                })
                .then(res => res.json())   
                .then(() => {
                    editedTds.forEach(td => td.classList.add('booked'));
                });
            }
        });
        
        // Generate shift table for cur or next month 
        document.querySelectorAll('form.generate-form').forEach(form => {
            form.addEventListener('submit', e => {
                e.preventDefault();
                const formId = form.id;
                let month;
                if (formId === "cur-generate-form") {
                    month = 'cur'
                } else if (formId === "next-generate-form") {
                    month = 'next'
                }
                fetch('/account/shifts/generate', {
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({'month': month}) 
                })
                .then(res => res.json())
                .then(data => {fillTable(data.graphic, data.booked)})
            });
        });

        // Clear generated names from shifts table
        document.querySelectorAll('form.clear-generated-form').forEach(form => {
            form.addEventListener('submit', e => {
                e.preventDefault();
                clearGenerated()
            });
        });

        document.querySelectorAll('form.clear-all-form').forEach(form => {
            form.addEventListener('submit', e => {
                e.preventDefault();
                const formId = form.id;
                let month;
                if (formId === "cur-clear-all-form") {
                    month = 'cur'
                } else if (formId === "next-clear-all-form") {
                    month = 'next'
                }
                fetch('/account/shifts/clear_all_shifts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({'month': month})  
                })
                .then(clearAll())
            });
        });
    });
};
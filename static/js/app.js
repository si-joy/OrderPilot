const body = document.body;
const root = document.documentElement;

const themeToggle = document.getElementById("themeToggle");
const themeIcon = document.getElementById("themeIcon");

const sidebarToggle = document.getElementById("sidebarToggle");
const sidebarOverlay = document.getElementById("sidebarOverlay");

function updateThemeIcon() {
    if (!themeIcon) {
        return;
    }

    const isDark = root.classList.contains("dark");

    themeIcon.textContent = isDark ? "☀" : "☾";
}

function toggleTheme() {
    const isDark = root.classList.toggle("dark");

    localStorage.setItem(
        "orderpilot-theme",
        isDark ? "dark" : "light"
    );

    updateThemeIcon();
}

if (themeToggle) {
    themeToggle.addEventListener("click", toggleTheme);
}

if (sidebarToggle) {
    sidebarToggle.addEventListener("click", function () {
        body.classList.toggle("sidebar-open");
    });
}

if (sidebarOverlay) {
    sidebarOverlay.addEventListener("click", function () {
        body.classList.remove("sidebar-open");
    });
}

window.addEventListener("resize", function () {
    if (window.innerWidth > 800) {
        body.classList.remove("sidebar-open");
    }
});

updateThemeIcon();


function setupOrderFormset() {
    const container = document.getElementById("orderItems");
    const addButton = document.getElementById("addOrderItem");
    const template = document.getElementById("emptyOrderItemTemplate");

    const totalForms = document.getElementById(
        "id_items-TOTAL_FORMS"
    );

    if (!container || !addButton || !template || !totalForms) {
        return;
    }

    addButton.addEventListener("click", function () {
        const formIndex = parseInt(
            totalForms.value,
            10
        );

        const html = template.innerHTML.replaceAll(
            "__prefix__",
            formIndex
        );

        const wrapper = document.createElement("div");

        wrapper.innerHTML = html.trim();

        const row = wrapper.firstElementChild;

        container.appendChild(row);

        totalForms.value = formIndex + 1;
    });


    container.addEventListener(
        "click",
        function (event) {
            const button = event.target.closest(
                ".remove-order-item"
            );

            if (!button) {
                return;
            }

            const row = button.closest(
                ".order-item-row"
            );

            if (!row) {
                return;
            }

            const deleteInput = row.querySelector(
                'input[name$="-DELETE"]'
            );

            if (deleteInput) {
                deleteInput.checked = true;
                row.style.display = "none";
            }
        }
    );
}


setupOrderFormset();


document.addEventListener(
    "DOMContentLoaded",
    function () {

        const notificationToggle =
            document.getElementById(
                "notificationToggle"
            );

        const notificationDropdown =
            document.getElementById(
                "notificationDropdown"
            );


        if (
            !notificationToggle
            || !notificationDropdown
        ) {
            return;
        }


        function openNotifications() {

            notificationDropdown.classList.add(
                "is-open"
            );

            notificationToggle.setAttribute(
                "aria-expanded",
                "true"
            );

            notificationDropdown.setAttribute(
                "aria-hidden",
                "false"
            );

        }


        function closeNotifications() {

            notificationDropdown.classList.remove(
                "is-open"
            );

            notificationToggle.setAttribute(
                "aria-expanded",
                "false"
            );

            notificationDropdown.setAttribute(
                "aria-hidden",
                "true"
            );

        }


        function toggleNotifications() {

            const isOpen =
                notificationDropdown
                    .classList
                    .contains(
                        "is-open"
                    );


            if (isOpen) {

                closeNotifications();

            } else {

                openNotifications();

            }

        }


        notificationToggle.addEventListener(
            "click",
            function (event) {

                event.preventDefault();
                event.stopPropagation();

                toggleNotifications();

            }
        );


        notificationDropdown.addEventListener(
            "click",
            function (event) {

                event.stopPropagation();

            }
        );


        document.addEventListener(
            "click",
            function () {

                closeNotifications();

            }
        );


        document.addEventListener(
            "keydown",
            function (event) {

                if (
                    event.key === "Escape"
                ) {

                    closeNotifications();

                }

            }
        );

    }
);
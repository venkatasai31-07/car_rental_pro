let selectedCar = "";
let selectedPrice = "";

document.querySelectorAll(".car-card").forEach(card => {
  card.addEventListener("click", () => {

    // remove previous selection
    document.querySelectorAll(".car-card")
      .forEach(c => c.classList.remove("selected"));

    // add selection
    card.classList.add("selected");

    // get data
    selectedCar = card.getAttribute("data-car");
    selectedPrice = card.getAttribute("data-price");

    // SAVE TO LOCAL STORAGE ✅
    localStorage.setItem("selectedCar", selectedCar);
    localStorage.setItem("selectedPrice", selectedPrice);

    // update UI
    document.getElementById("selectedInfo").innerHTML =
      `Selected Car: <span>${selectedCar} (${selectedPrice})</span>`;
  });
});

function proceedBooking() {
  if (!selectedCar) {
    alert("Please select a car first");
    return;
  }

  // redirect
  window.location.href = "../booking.html";
}

---
name: tesco
description: Build a grocery basket on tesco.ie with ego-browser. Search items, add a default item, read the basket total, empty the basket. Never pay.
---

# Tesco basket (tesco.ie)

Load the ego-browser skill first (`ego-browser skill`). Use one task space for the whole request. Never open the payment page. Never type card data.

## Sign-in
Adding to the basket needs a signed-in Tesco account. The first Add click on a signed-out browser redirects to `https://www.tesco.ie/account/login/en-IE`. Do not enter credentials. Call `await task.handOff()`, tell the user to sign in in the browser, then resume with `takeOverTaskSpace(id)` after the user confirms.

## Steps
Verified by hand: 1, 2, 3 (up to the sign-in redirect). Steps 4 to 6 are written from the page structure and must be checked on the first signed-in run.

1. **Open search.** `page.goto("https://www.tesco.ie/shop/en-IE/search?query=<item>")`. On first load a consent banner shows: click `text="Reject all"`.
2. **Read the results.** Each result is a `list_item` with a product link (`/shop/en-IE/products/<id>`), a price (`EUR x.xx`), a unit price (`/litre`, `/kg`) and a button named `add 1 <product name>` (`loc=css:button[aria-label="add 1 <product name>"]`).
3. **Pick the default item.** Take the first result whose name starts with `Tesco` (own brand) and that has a plain, single-unit size: milk `Tesco Fresh Milk 1ltr`, eggs `Tesco Free Range Eggs 12 pack` style, bread `Tesco Soft White Sliced`/`Tesco Wholemeal` style loaf. Skip multipacks, organic, "Finest" and sponsored results. Note the name and price.
4. **Add to basket.** Click the `add 1 <name>` button once. Wait for the Basket Summary output to change from the previous value.
5. **Read the total.** The `Basket Summary` container (right column on search pages) holds the guide price (`output` with `EUR x.xx` and `Guide price`). Open `https://www.tesco.ie/shop/en-IE/trolley` to list the items and quantities; the total is shown there too. Read it with `page.snapshot({scope: "full_page"})`.
6. **Empty the basket.** On the trolley page remove each line (decrease the quantity to 0 with the item's quantity controls, or use the "Remove"/"Empty trolley" control if shown). Reload the trolley and confirm the basket total is `EUR 0.00` before reporting done.

## Do not
- Click `Checkout`.
- Open any URL under a payment or checkout path.
- Guess the sign-in. Hand off to the user.

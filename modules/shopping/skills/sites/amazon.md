# Site note: Amazon Ireland (amazon.ie)

Page steps for the `shopping` skill. Read it first. Observed 12 Nov 2026, signed out, guest, location Dublin D14. Use amazon.ie; `.co.uk` only if .ie does not sell it.

1. Search: `https://www.amazon.ie/s?k=office+chair`. No consent banner appeared.
2. Results are `div[data-component-type="s-search-result"]` with `data-asin`. Skip ones with `.puis-sponsored-label-text`. Title in `h2`, price in `.a-price .a-offscreen`. Read the first three to six with `page.evaluate`.
3. Product page: `https://www.amazon.ie/dp/<asin>`. Title `#productTitle`, price `#corePrice_feature_div .a-offscreen`, button `loc=css:#add-to-cart-button` ("Add to basket").
4. Add worked signed out. No sign-in was asked. It lands on `/cart/smart-wagon?newItems=...`.
5. Cart: `https://www.amazon.ie/gp/cart/view.html`. Items carry `data-asin`. Total text is "Subtotal (1 item): EUR 65.99" in the page text. The nav badge `#nav-cart-count` shows the count. The button "Proceed to checkout" is the boundary: do not click it.
6. Remove one item: `loc=css:[data-asin="<asin>"] input[data-action="delete-active"]`. The empty-text wait timed out; reload the cart and check `#nav-cart-count` = 0 and no `data-asin` rows.
7. Sign-in (`/ap/signin`) is Arjun's: `task.handOff()`.

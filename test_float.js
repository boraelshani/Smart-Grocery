
const it = { price: '2.50' };
const raw_price = (it.price_val !== undefined ? it.price_val : it.price || 0);
const unit = parseFloat(raw_price) || 0;
console.log(unit);


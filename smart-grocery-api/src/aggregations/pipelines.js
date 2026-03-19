export const buildCategoryExplorerPipeline = ({
  categoryPath,
  brandId,
  labels,
  minPrice,
  maxPrice,
  storeId,
  sortBy,
  skip,
  limit
}) => {
  const productMatch = {};
  const storeProductMatch = { isAvailable: true };

  if (categoryPath?.length) {
    productMatch.categoryPath = { $all: categoryPath };
  }
  if (brandId) {
    productMatch.brandId = brandId;
  }
  if (labels?.length) {
    productMatch.labels = { $in: labels };
  }
  if (storeId) {
    storeProductMatch.storeId = storeId;
  }
  if (minPrice !== undefined || maxPrice !== undefined) {
    storeProductMatch.$expr = {
      $and: [
        minPrice !== undefined
          ? { $gte: [{ $ifNull: ["$promoPrice", "$basePrice"] }, minPrice] }
          : { $literal: true },
        maxPrice !== undefined
          ? { $lte: [{ $ifNull: ["$promoPrice", "$basePrice"] }, maxPrice] }
          : { $literal: true }
      ]
    };
  }

  const sortMap = {
    cheapest: { cheapestPrice: 1, createdAt: -1 },
    newest: { createdAt: -1 },
    popular: { "metrics.popularityScore": -1, createdAt: -1 }
  };

  return [
    { $match: productMatch },
    {
      $lookup: {
        from: "storeproducts",
        let: { pid: "$productId" },
        pipeline: [
          { $match: { $expr: { $eq: ["$productId", "$$pid"] } } },
          { $match: storeProductMatch },
          {
            $addFields: {
              effectivePrice: { $ifNull: ["$promoPrice", "$basePrice"] }
            }
          },
          { $sort: { effectivePrice: 1 } }
        ],
        as: "offers"
      }
    },
    { $match: { offers: { $ne: [] } } },
    {
      $lookup: {
        from: "productmetrics",
        localField: "productId",
        foreignField: "productId",
        as: "metrics"
      }
    },
    {
      $addFields: {
        metrics: { $ifNull: [{ $arrayElemAt: ["$metrics", 0] }, {}] },
        cheapestPrice: {
          $min: {
            $map: {
              input: "$offers",
              as: "offer",
              in: { $ifNull: ["$$offer.promoPrice", "$$offer.basePrice"] }
            }
          }
        }
      }
    },
    { $sort: sortMap[sortBy] || sortMap.cheapest },
    { $skip: skip },
    { $limit: limit }
  ];
};

export const cheapestStorePipeline = () => [
  {
    $addFields: {
      effectivePrice: { $ifNull: ["$promoPrice", "$basePrice"] }
    }
  },
  { $match: { isAvailable: true } },
  { $sort: { productId: 1, effectivePrice: 1, lastPriceUpdate: -1 } },
  {
    $group: {
      _id: "$productId",
      cheapestStoreProductId: { $first: "$storeProductId" },
      cheapestPrice: { $first: "$effectivePrice" }
    }
  }
];

export const popularProductsPipeline = (days = 30) => {
  const dateThreshold = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
  return [
    { $match: { updatedAt: { $gte: dateThreshold } } },
    { $sort: { popularityScore: -1, trendScore: -1 } },
    { $limit: 100 }
  ];
};

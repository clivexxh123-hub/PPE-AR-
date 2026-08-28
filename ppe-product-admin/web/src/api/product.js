import request from "./request";

export function getCategories(config = {}) {
  return request({
    url: "/categories",
    method: "get",
    ...config
  });
}

export function getProducts(params, config = {}) {
  return request({
    url: "/products",
    method: "get",
    params,
    ...config
  });
}

export function getProductDetail(id) {
  return request({
    url: `/products/${id}`,
    method: "get"
  });
}

export function updateProduct(id, data) {
  return request({
    url: `/products/${id}`,
    method: "put",
    data
  });
}

export function uploadProductFile(id, data) {
  return request({
    url: `/products/${id}/files`,
    method: "post",
    data,
    headers: {
      "Content-Type": "multipart/form-data"
    }
  });
}

export function deleteProductFile(id) {
  return request({
    url: `/files/${id}`,
    method: "delete"
  });
}

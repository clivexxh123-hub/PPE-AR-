class ProductShowcaseRepository {
    constructor(executor) {
        this.executor = executor;
    }

    async upsert(productId, profile) {
        await this.executor.query(
            `INSERT INTO business_product_showcase_profiles (
                product_id, material, unit_name, specification,
                packaging_specification, execution_standard, selling_points_json
             ) VALUES (?, ?, ?, ?, ?, ?, ?)
             ON DUPLICATE KEY UPDATE
                material=VALUES(material),
                unit_name=VALUES(unit_name),
                specification=VALUES(specification),
                packaging_specification=VALUES(packaging_specification),
                execution_standard=VALUES(execution_standard),
                selling_points_json=VALUES(selling_points_json)`,
            [
                productId,
                profile.material,
                profile.unitName,
                profile.specification,
                profile.packagingSpecification,
                profile.executionStandard,
                JSON.stringify(profile.sellingPoints)
            ]
        );
    }

    async findByProductId(productId) {
        const [rows] = await this.executor.query(
            `SELECT product_id, material, unit_name, specification,
                    packaging_specification, execution_standard, selling_points_json
             FROM business_product_showcase_profiles
             WHERE product_id=? LIMIT 1`,
            [productId]
        );
        return rows[0] || null;
    }
}

module.exports = { ProductShowcaseRepository };

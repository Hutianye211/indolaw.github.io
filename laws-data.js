// 印尼投资法律法规数据库
// 添加新法规只需在 laws 数组中添加新对象即可

const laws = [
    {
        id: 1,
        title: "投资法 2007年第25号",
        number: "Law No. 25/2007",
        category: "investment",  // 可选值: investment, company, tax, labor, trade
        date: "2007-04-26",
        summary: "规范印尼境内外国投资和国内投资的基本法律框架",
        originalLink: "https://peraturan.bpk.go.id/Details/xxxxx",  // 可选字段，法规原文链接
        content: `
            <h3>法律背景</h3>
            <p>在这里填写详细内容...</p>
            
            <h3>主要内容</h3>
            <p>继续填写...</p>
            
            <h3>核心条款</h3>
            <ul>
                <li>第一条内容</li>
                <li>第二条内容</li>
            </ul>
        `
    },
    {
        id: 2,
        title: "创造就业综合法 2020年第11号",
        number: "Law No. 11/2020",
        category: "labor",
        date: "2020-11-02",
        summary: "全面改革印尼劳动、投资、营商环境的综合性法律",
        originalLink: "https://jdih.setkab.go.id/xxxxx",  // 如果没有链接可以省略这一行
        content: `
            <h3>立法背景</h3>
            <p>俗称"Omnibus Law"...</p>
            
            <h3>主要改革领域</h3>
            <p>在这里详细说明...</p>
        `
    },
    {
        id: 3,
        title: "有限责任公司法 2007年第40号",
        number: "Law No. 40/2007",
        category: "company",
        date: "2007-08-16",
        summary: "规范有限责任公司设立、运营、解散的法律依据",
        // 没有原链接时可以不写 originalLink 字段
        content: `
            <h3>法律概述</h3>
            <p>你的详细内容...</p>
        `
    }
    
    // 在这里继续添加更多法规...
    // 复制上面的格式，修改 id（递增）和其他字段即可
];

// 注意事项：
// 1. 每个法规的 id 必须唯一且递增
// 2. category 必须是这5个之一: investment, company, tax, labor, trade
// 3. originalLink 是可选字段，有原文链接就填，没有可以省略
// 4. content 中可以使用 HTML 标签: <h3>, <p>, <ul>, <li>, <ol>, <strong> 等
// 5. 日期格式: YYYY-MM-DD
// 6. 保存时确保文件编码为 UTF-8

// 印尼官方法规网站参考：
// - https://peraturan.bpk.go.id/ (国家审计署法规库)
// - https://jdih.setkab.go.id/ (内阁秘书处法律文件)
// - https://peraturan.go.id/ (统一法规门户)

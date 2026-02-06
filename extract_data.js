// 数据提取脚本
function extractItemData() {
    let result = "品项编号,品项名称,价格,状态\n";
    
    // 尝试查找表格
    const tables = document.querySelectorAll('table');
    console.log('找到表格数量:', tables.length);
    
    for(let table of tables) {
        const rows = table.querySelectorAll('tr');
        if(rows.length > 5) { // 假设有数据的表格至少有5行
            console.log('处理表格，行数:', rows.length);
            
            // 提取数据
            for(let i = 1; i < rows.length; i++) {
                const cells = rows[i].querySelectorAll('td');
                if(cells.length >= 3) {
                    const code = cells[0]?.innerText.trim() || '';
                    const name = cells[1]?.innerText.trim() || '';
                    const price = cells[2]?.innerText.trim() || '';
                    const status = cells[3]?.innerText.trim() || '';
                    
                    result += `${code},${name},${price},${status}\n`;
                }
            }
            break;
        }
    }
    
    return result;
}

// 执行提取
const data = extractItemData();
console.log('提取到数据行数:', data.split('\\n').length - 1);
console.log('前几行数据:', data.substring(0, 500));

// 创建下载链接
const blob = new Blob([data], {type: 'text/csv;charset=utf-8;'});
const url = URL.createObjectURL(blob);
const link = document.createElement('a');
link.href = url;
link.download = '品项数据.csv';
link.style.display = 'none';
document.body.appendChild(link);
link.click();
document.body.removeChild(link);
URL.revokeObjectURL(url);

console.log('数据已导出');
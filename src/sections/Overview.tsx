import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, Typography, Card, CardHeader, CardContent, Grid, FormGroup, Switch, FormControlLabel } from '@mui/material';
import { AbstractSection, SectionProps } from '../common';


interface OverviewDataRow {
    ticker: string;
    type: string;
    currency: string;
    last_price: number;
    average_price: number;
    investment: number;
    volume: number;
    value: number;
    fees: number;
    clean_profit: number;
    fx_profit: number;
    total_profit: number;
    rewards: number;
    dividends: number;
    dividend_currency: string;
}

interface DividendsDataRow {
    ticker: string;
    currency: string;
    dividends: number;
}

type OverviewResponse = Array<OverviewDataRow>;
type DividendsResponse = {[ticker:string]:DividendsDataRow};

interface OverviewState {
    investment: number;
    fees: number;
    value: number;
    profit: number;
    savingsDeposit: number;
    savingsValue: number;
    overview: Array<OverviewDataRow>;
    dividends: DividendsResponse;
    types: Array<string>;
    groupByType: boolean;
}

interface OverviewProps {}

export class Overview extends AbstractSection<OverviewProps, OverviewState> {

    sectionName = () => 'Overview';

    constructor(props: OverviewProps & SectionProps) {
        super(props);
        this.state = {
            investment: 0,
            fees: 0,
            value: 0,
            profit: 0,
            savingsDeposit: 0,
            savingsValue: 0,
            overview: [],
            dividends: {},
            types: [],
            groupByType: false,
        };
    }

    componentDidMount() {
        super.componentDidMount();
        this.props.displayProgressBar(true)
        this.loadOverview().then(() =>
            this.loadDividends().then(() =>
                this.props.displayProgressBar(false)
            )
        );
    }

    loadOverview() {
        return fetch('/overview/get')
            .then<OverviewResponse>(res => res.json())
            .then(overview => {
                const types: Array<string> = [];
                overview.forEach(v => {
                    if (!types.includes(v.type)) types.push(v.type);
                });
                types.sort();
                this.setState({
                    overview,
                    types,
                    investment: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev : prev + cur.investment, 0),
                    fees: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev : prev + cur.fees, 0),
                    value: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev : prev + cur.value, 0),
                    profit: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev : prev + cur.total_profit, 0),
                    savingsDeposit: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev + cur.investment : prev, 0),
                    savingsValue: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev + cur.value : prev, 0),
                });
            });
    }

    loadDividends() {
        return fetch('/dividends/calc')
            .then<DividendsResponse>(res => res.json())
            .then(dividends => {
                this.setState({dividends});
            });
    }

    render() {
        return (
            <Box>
                <Grid container spacing={2}>
                    <Grid item xs={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Investment'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.investment)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Fees'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.fees)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Value'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.value)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Profit'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.profit)} ({this.formatPercents(this.state.profit/this.state.investment)})
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Savings Deposit'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.savingsDeposit)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Savings Value'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.savingsValue)} ({this.formatPercents((this.state.savingsValue-this.state.savingsDeposit)/this.state.savingsValue)})
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>

                <FormGroup>
                    <FormControlLabel control={<Switch checked={this.state.groupByType} onChange={(e, value) => this.setState({groupByType: value})}/>} label="Group by type" />
                </FormGroup>

                {this.state.groupByType ?
                    this.state.types.map(type =>
                        <Card elevation={3} sx={{marginBottom: '1em'}}>
                            <CardHeader title={type} />
                            <CardContent>
                                <TableContainer>
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell>Ticker</TableCell>
                                                <TableCell align='right'>Last price</TableCell>
                                                <TableCell align='right'>Avg price</TableCell>
                                                <TableCell align='center'>Volume</TableCell>
                                                <TableCell align='right'>Invested</TableCell>
                                                <TableCell align='right'>Fee</TableCell>
                                                <TableCell align='right'>Value</TableCell>
                                                <TableCell colSpan={2} align='center'>Profit</TableCell>
                                                <TableCell colSpan={2} align='center'>Dividends</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {this.state.overview.filter(item => item.type === type).map((item, i) =>
                                                <TableRow key={i} sx={{backgroundColor: item.total_profit < 0 ? 'rgba(255,0,0,0.25)' : 'rgba(0,255,0,0.25)'}}>
                                                    <TableCell>{item.ticker}</TableCell>
                                                    <TableCell align='right'>{this.formatCurrency(item.last_price, item.currency)}</TableCell>
                                                    <TableCell align='right'>{this.formatCurrency(item.average_price, item.currency)}</TableCell>
                                                    <TableCell align='center'>{item.volume ? item.volume : null}</TableCell>
                                                    <TableCell align='right'>{this.formatCurrency(item.investment)}</TableCell>
                                                    <TableCell align='right'>{this.formatCurrency(item.fees)}</TableCell>
                                                    <TableCell align='right'>{this.formatCurrency(item.value)}</TableCell>
                                                    <TableCell align='right'>{this.formatCurrency(item.total_profit)}</TableCell>
                                                    <TableCell align='right'>{this.formatPercents(item.total_profit/item.investment)}</TableCell>
                                                    <TableCell align='right'>{this.state.dividends[item.ticker] ? this.formatCurrency(this.state.dividends[item.ticker].dividends, this.state.dividends[item.ticker].currency) : null}</TableCell>
                                                    <TableCell align='right'>{item.dividends ? this.formatCurrency(item.dividends, item.dividend_currency) : null}</TableCell>
                                                </TableRow>
                                            )}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </CardContent>
                        </Card>
                    ) :
                    <Card elevation={3}>
                        <CardContent>
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Ticker</TableCell>
                                            <TableCell align='right'>Last price</TableCell>
                                            <TableCell align='right'>Avg price</TableCell>
                                            <TableCell align='center'>Volume</TableCell>
                                            <TableCell align='right'>Invested</TableCell>
                                            <TableCell align='right'>Fee</TableCell>
                                            <TableCell align='right'>Value</TableCell>
                                            <TableCell colSpan={2} align='center'>Profit</TableCell>
                                            <TableCell colSpan={2} align='center'>Dividends</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {this.state.overview.map((item, i) =>
                                            <TableRow key={i} sx={{backgroundColor: item.total_profit < 0 ? 'rgba(255,0,0,0.25)' : 'rgba(0,255,0,0.25)'}}>
                                                <TableCell>{item.ticker}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(item.last_price, item.currency)}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(item.average_price, item.currency)}</TableCell>
                                                <TableCell align='center'>{item.volume ? item.volume : null}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(item.investment)}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(item.fees)}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(item.value)}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(item.total_profit)}</TableCell>
                                                <TableCell align='right'>{this.formatPercents(item.total_profit/item.investment)}</TableCell>
                                                <TableCell align='right'>{this.state.dividends[item.ticker] ? this.formatCurrency(this.state.dividends[item.ticker].dividends, this.state.dividends[item.ticker].currency) : null}</TableCell>
                                                <TableCell align='right'>{item.dividends ? this.formatCurrency(item.dividends, item.dividend_currency) : null}</TableCell>
                                            </TableRow>
                                        )}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </CardContent>
                    </Card>
                }
            </Box>
        )
    }
}